from flask import Flask, jsonify, request, send_file
import requests
import os
import re
from datetime import datetime
from urllib.parse import urlparse
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure
from bson import ObjectId
app = Flask(__name__)


# MongoDB connection
MONGO_URI = os.getenv("MONGO_URI", "mongodb://mongodb:27017/")
DB_NAME = os.getenv("DB_NAME", "petstore")
STORE_ID = os.getenv("STORE_ID", "1")

client = MongoClient(MONGO_URI)
db = client[DB_NAME]  # Same database for all stores
pet_types_collection = db.pet_types
pets_collection = db.pets


# API configuration
NINJA_API_KEY = os.getenv("NINJA_API_KEY", "UjA4kHG33oEofOpk4au2sg==Hm3gGGdRuu6njeG5")  # Use env var or fallback
NINJA_API_URL = "https://api.api-ninjas.com/v1/animals"

# Image storage directory
IMAGE_DIR = "images"
if not os.path.exists(IMAGE_DIR):
    os.makedirs(IMAGE_DIR)

# Basic route to test that the server is running
@app.route("/", methods=["GET"])
def home():
    return jsonify({"message": "Pet Store API is running"}), 200

@app.route("/pet-types", methods=["GET"])
def get_pet_types():
    try:
        # Build base query with store filter
        mongo_query = {"store_id": STORE_ID}  # Keep as string to match what we store
        
        # Add filters from URL parameters
        for key, value in request.args.items():
            if key == "hasAttribute":
                # Better: Use $elemMatch for case-insensitive array search
                mongo_query["attributes"] = {
                    "$elemMatch": {"$regex": f"^{value}$", "$options": "i"}
                }
            elif key == "id":
                # Convert string ID to ObjectId for filtering
                try:
                    mongo_query["_id"] = ObjectId(value)
                except:
                    # Invalid ObjectId format - no results will match
                    mongo_query["_id"] = None
            elif key in ["type", "family", "genus"]:
                # Case-insensitive exact matching
                mongo_query[key] = {"$regex": f"^{value}$", "$options": "i"}
            elif key == "lifespan":
                # Handle both numeric and string lifespan
                if value.isdigit():
                    mongo_query[key] = int(value)
                else:
                    mongo_query[key] = {"$regex": f"^{value}$", "$options": "i"}
        
        # Query with field exclusion
        pet_types = list(pet_types_collection.find(
            mongo_query, 
            {"store_id": 0}  # Only exclude store_id, keep _id for conversion
        ))
        
        # Convert _id to id for each pet type
        for pet_type in pet_types:
            pet_type["id"] = str(pet_type["_id"])
            pet_type.pop("_id")
        
        return jsonify(pet_types), 200
    except Exception as e:
        return jsonify({"error": "Database error"}), 500

def fetch_animal_info(animal_name):
    """Fetch animal information from Ninja API"""
    try:
        headers = {
            'X-Api-Key': NINJA_API_KEY
        }
        response = requests.get(f"{NINJA_API_URL}?name={animal_name}", headers=headers)
        
        if response.status_code == 200:
            animals = response.json()
            # Find exact match (case insensitive)
            for animal in animals:
                if animal.get('name', '').lower() == animal_name.lower():
                    return animal
            return None
        else:
            return response.status_code
    except:
        return 500

def parse_lifespan(lifespan_str):
    """Parse lifespan string to get the minimum number"""
    if not lifespan_str:
        return None
    
    # Extract all numbers from the string
    numbers = re.findall(r'\d+', lifespan_str)
    if numbers:
        return int(numbers[0])  # Return the first (lowest) number
    return None

def parse_attributes(animal_data):
    """Parse temperament or group_behavior into attributes array"""
    # Prefer temperament over group_behavior
    text = animal_data.get('characteristics', {}).get('temperament')
    if not text:
        text = animal_data.get('characteristics', {}).get('group_behavior')
    
    if not text:
        return []
    
    # Split into words and remove punctuation
    words = re.findall(r'\w+', text)
    return words

@app.route("/pet-types", methods=["POST"])
def post_pet_types():
    try:
        # Check that the request is JSON
        if not request.is_json:
            return jsonify({"error": "Expected application/json media type"}), 415

        # Try to read the JSON body
        data = request.get_json(silent=True)
        if data is None:
            return jsonify({"error": "Malformed data"}), 400

        # Validate that "type" exists and is a string
        if "type" not in data or not isinstance(data["type"], str):
            return jsonify({"error": "Malformed data"}), 400

        animal_type = data["type"].strip()
        
        # Check if this pet type already exists in this store
        existing_type = pet_types_collection.find_one({
            "store_id": STORE_ID,
            "type": {"$regex": f"^{animal_type}$", "$options": "i"}
        })
        if existing_type:
            return jsonify({"error": "Malformed data"}), 400

        # Fetch animal info from Ninja API
        result = fetch_animal_info(animal_type)

        # Case 1: API error (401/403/500)
        if isinstance(result, int) and result != 200:
            return jsonify({"server error": f"API response code {result}"}), 500

        # Case 2: type not found in Ninja → malformed data
        if result is None:
            return jsonify({"error": "Malformed data"}), 400

        # Case 3: success
        animal_info = result

        # Extract information from Ninja API response
        taxonomy = animal_info.get('taxonomy', {})
        characteristics = animal_info.get('characteristics', {})
        
        family = taxonomy.get('family', '')
        genus = taxonomy.get('genus', '')
        attributes = parse_attributes(animal_info)
        lifespan = parse_lifespan(characteristics.get('lifespan'))

        # Build the pet-type object (no custom id needed)
        pet_type_obj = {
            "type": animal_type,
            "family": family,
            "genus": genus,
            "attributes": attributes,
            "lifespan": lifespan,
            "pets": [],
            "store_id": STORE_ID
        }

        # Save to MongoDB and get the inserted_id
        result = pet_types_collection.insert_one(pet_type_obj)
        
        # Use MongoDB's _id as our id
        pet_type_obj["id"] = str(result.inserted_id)
        pet_type_obj.pop('_id', None)
        pet_type_obj.pop('store_id', None)
        return jsonify(pet_type_obj), 201
    except Exception as e:
        return jsonify({"error": "Database error"}), 500

@app.route("/pet-types/<pet_type_id>", methods=["GET"])
def get_pet_type(pet_type_id):
    try:
        # Convert string ID to ObjectId
        try:
            object_id = ObjectId(pet_type_id)
        except:
            return jsonify({"error": "Not found"}), 404
            
        pet_type = pet_types_collection.find_one(
            {"_id": object_id, "store_id": STORE_ID}
        )
        if not pet_type:
            return jsonify({"error": "Not found"}), 404
        
        # Convert _id to string id for response
        pet_type["id"] = str(pet_type["_id"])
        pet_type.pop("_id")
        pet_type.pop("store_id")
        
        return jsonify(pet_type), 200
    except Exception as e:
        return jsonify({"error": "Database error"}), 500

@app.route("/pet-types/<pet_type_id>", methods=["DELETE"])
def delete_pet_type(pet_type_id):
    try:
        # Convert string ID to ObjectId
        try:
            object_id = ObjectId(pet_type_id)
        except:
            return jsonify({"error": "Not found"}), 404
            
        pet_type = pet_types_collection.find_one({"_id": object_id, "store_id": STORE_ID})
        if not pet_type:
            return jsonify({"error": "Not found"}), 404
        
        # Check if pet-type has pets
        if pet_type["pets"]:
            return jsonify({"error": "Malformed data"}), 400
        
        # Delete the pet-type and all its pets
        pet_types_collection.delete_one({"_id": object_id, "store_id": STORE_ID})
        pets_collection.delete_many({"pet_type_id": pet_type_id, "store_id": STORE_ID})
        
        return "", 204
    except Exception as e:
        return jsonify({"error": "Database error"}), 500

def download_image(url, filename):
    """Download image from URL and save to local file"""
    try:
        response = requests.get(url)
        if response.status_code == 200:
            filepath = os.path.join(IMAGE_DIR, filename)
            with open(filepath, 'wb') as f:
                f.write(response.content)
            return True
        return False
    except:
        return False

def parse_date_range(date_str):
    """Parse date string and return datetime object"""
    try:
        return datetime.strptime(date_str, "%d-%m-%Y")
    except:
        return None

@app.route("/pet-types/<pet_type_id>/pets", methods=["GET"])
def get_pets(pet_type_id):
    try:
        # Convert string ID to ObjectId
        try:
            object_id = ObjectId(pet_type_id)
        except:
            return jsonify({"error": "Not found"}), 404
            
        pet_type = pet_types_collection.find_one({"_id": object_id, "store_id": STORE_ID})
        if not pet_type:
            return jsonify({"error": "Not found"}), 404
        
        # Build MongoDB query with store and pet type filters
        mongo_query = {"pet_type_id": pet_type_id, "store_id": STORE_ID}
        
        # Handle query parameters for date filtering
        birth_date_gt = request.args.get('birthdateGT')
        birth_date_lt = request.args.get('birthdateLT')
        
        # For date filtering, we need to fetch and filter in Python since 
        # birthdates are stored as strings in "dd-mm-yyyy" format
        # and MongoDB string comparison won't work for date ranges
        filter_dates = birth_date_gt or birth_date_lt
        
        pets = list(pets_collection.find(
            mongo_query, 
            {"_id": 0, "pet_type_id": 0, "store_id": 0}
        ))
        
        # Apply date filtering in Python if needed
        if filter_dates:
            filtered_pets = []
            for pet in pets:
                if pet['birthdate'] == 'NA':
                    continue
                
                pet_date = parse_date_range(pet['birthdate'])
                if not pet_date:
                    continue
                
                include_pet = True
                
                if birth_date_gt:
                    gt_date = parse_date_range(birth_date_gt)
                    if gt_date and pet_date <= gt_date:
                        include_pet = False
                
                if birth_date_lt:
                    lt_date = parse_date_range(birth_date_lt)
                    if lt_date and pet_date >= lt_date:
                        include_pet = False
                
                if include_pet:
                    filtered_pets.append(pet)
            
            pets = filtered_pets
        
        return jsonify(pets), 200
    except Exception as e:
        return jsonify({"error": "Database error"}), 500

@app.route("/pet-types/<pet_type_id>/pets", methods=["POST"])
def post_pet(pet_type_id):
    try:
        # Convert string ID to ObjectId
        try:
            object_id = ObjectId(pet_type_id)
        except:
            return jsonify({"error": "Not found"}), 404
            
        pet_type = pet_types_collection.find_one({"_id": object_id, "store_id": STORE_ID})
        if not pet_type:
            return jsonify({"error": "Not found"}), 404
        
        if not request.is_json:
            return jsonify({"error": "Expected application/json media type"}), 415

        data = request.get_json(silent=True)
        if data is None:
            return jsonify({"error": "Malformed data"}), 400

        # Validate required name field
        if "name" not in data or not isinstance(data["name"], str):
            return jsonify({"error": "Malformed data"}), 400

        pet_name = data["name"].strip()
        
        # Check if pet with this name already exists for this type in this store
        existing_pet = pets_collection.find_one({
            "pet_type_id": pet_type_id, 
            "name": pet_name,
            "store_id": STORE_ID
        })
        if existing_pet:
            return jsonify({"error": "Malformed data"}), 400

        # Handle optional fields
        birthdate = data.get("birthdate")
        if birthdate is None:
            birthdate = data.get("birthdate:")
        if birthdate is None:
            birthdate = "NA"

        picture_url = data.get('picture-url')
        picture_filename = 'NA'
        
        # Download image if URL provided
        if picture_url and picture_url.strip():
            # Generate unique filename
            parsed_url = urlparse(picture_url)
            ext = os.path.splitext(parsed_url.path)[1].lower()

            # Convert .jpeg → .jpg and enforce only .jpg/.png for schema compliance
            if ext == ".jpeg":
                ext = ".jpg"
            if ext not in [".jpg", ".png"]:
                ext = ".jpg"
            picture_filename = f"{pet_name}-{pet_type['type'].replace(' ', '')}{ext}"
            
            if download_image(picture_url, picture_filename):
                pass  # Successfully downloaded
            else:
                picture_filename = 'NA'

        # Create pet object
        pet_obj = {
            "name": pet_name,
            "birthdate": birthdate,
            "picture": picture_filename,
            "pet_type_id": pet_type_id,
            "store_id": STORE_ID
        }

        # Save to MongoDB
        pets_collection.insert_one(pet_obj)
        
        # Update pet-type's pets list
        pet_types_collection.update_one(
            {"_id": object_id, "store_id": STORE_ID},
            {"$push": {"pets": pet_name}}
        )

        # Remove MongoDB fields and return
        pet_obj.pop('_id', None)
        pet_obj.pop('pet_type_id', None)
        pet_obj.pop('store_id', None)
        return jsonify(pet_obj), 201
    except Exception as e:
        return jsonify({"error": "Database error"}), 500

@app.route("/pet-types/<pet_type_id>/pets/<pet_name>", methods=["GET"])
def get_pet(pet_type_id, pet_name):
    try:
        # Convert string ID to ObjectId
        try:
            object_id = ObjectId(pet_type_id)
        except:
            return jsonify({"error": "Not found"}), 404
            
        pet_type = pet_types_collection.find_one({"_id": object_id, "store_id": STORE_ID})
        if not pet_type:
            return jsonify({"error": "Not found"}), 404
        
        pet = pets_collection.find_one(
            {"pet_type_id": pet_type_id, "name": pet_name, "store_id": STORE_ID}, 
            {"_id": 0, "pet_type_id": 0, "store_id": 0}
        )
        if not pet:
            return jsonify({"error": "Not found"}), 404
        
        return jsonify(pet), 200
    except Exception as e:
        return jsonify({"error": "Database error"}), 500

@app.route("/pet-types/<pet_type_id>/pets/<pet_name>", methods=["DELETE"])
def delete_pet(pet_type_id, pet_name):
    try:
        # Convert string ID to ObjectId
        try:
            object_id = ObjectId(pet_type_id)
        except:
            return jsonify({"error": "Not found"}), 404
            
        pet_type = pet_types_collection.find_one({"_id": object_id, "store_id": STORE_ID})
        if not pet_type:
            return jsonify({"error": "Not found"}), 404
        
        pet = pets_collection.find_one({
            "pet_type_id": pet_type_id, 
            "name": pet_name,
            "store_id": STORE_ID
        })
        if not pet:
            return jsonify({"error": "Not found"}), 404
        
        # Delete associated image file if it exists
        if pet["picture"] != "NA":
            image_path = os.path.join(IMAGE_DIR, pet["picture"])
            if os.path.exists(image_path):
                os.remove(image_path)
        
        # Remove from MongoDB
        pets_collection.delete_one({
            "pet_type_id": pet_type_id, 
            "name": pet_name,
            "store_id": STORE_ID
        })
        
        # Remove from pet-type's pets list
        pet_types_collection.update_one(
            {"_id": object_id, "store_id": STORE_ID},
            {"$pull": {"pets": pet_name}}
        )
        
        return "", 204
    except Exception as e:
        return jsonify({"error": "Database error"}), 500

@app.route("/pet-types/<pet_type_id>/pets/<pet_name>", methods=["PUT"])
def put_pet(pet_type_id, pet_name):
    try:
        # Convert string ID to ObjectId
        try:
            object_id = ObjectId(pet_type_id)
        except:
            return jsonify({"error": "Not found"}), 404
            
        pet_type = pet_types_collection.find_one({"_id": object_id, "store_id": STORE_ID})
        if not pet_type:
            return jsonify({"error": "Not found"}), 404
        
        current_pet = pets_collection.find_one({
            "pet_type_id": pet_type_id, 
            "name": pet_name,
            "store_id": STORE_ID
        })
        if not current_pet:
            return jsonify({"error": "Not found"}), 404
        
        if not request.is_json:
            return jsonify({"error": "Expected application/json media type"}), 415

        data = request.get_json(silent=True)
        if data is None:
            return jsonify({"error": "Malformed data"}), 400

        # Validate required name field
        if "name" not in data or not isinstance(data["name"], str):
            return jsonify({"error": "Malformed data"}), 400

        new_name = data["name"].strip()
        
        # If name is changing, check it doesn't conflict
        if new_name != pet_name:
            existing_pet = pets_collection.find_one({
                "pet_type_id": pet_type_id, 
                "name": new_name,
                "store_id": STORE_ID
            })
            if existing_pet:
                return jsonify({"error": "Malformed data"}), 400
        
        # Handle optional fields
        birthdate = data.get('birthdate', current_pet['birthdate'])
        picture_url = data.get('picture-url')
        picture_filename = current_pet['picture']
        
        # Handle image update
        if picture_url and picture_url.strip():
            parsed_url = urlparse(picture_url)
            ext = os.path.splitext(parsed_url.path)[1] or '.jpg'
            new_picture_filename = f"{new_name}-{pet_type['type'].replace(' ', '')}{ext}"
            
            if download_image(picture_url, new_picture_filename):
                # Delete old image if it exists and is different
                if picture_filename != "NA" and picture_filename != new_picture_filename:
                    old_path = os.path.join(IMAGE_DIR, picture_filename)
                    if os.path.exists(old_path):
                        os.remove(old_path)
                picture_filename = new_picture_filename

        # Update pet in MongoDB
        pets_collection.update_one(
            {"pet_type_id": pet_type_id, "name": pet_name, "store_id": STORE_ID},
            {"$set": {
                "name": new_name,
                "birthdate": birthdate,
                "picture": picture_filename
            }}
        )
        
        # Update pet-type's pets list if name changed
        if new_name != pet_name:
            pet_types_collection.update_one(
                {"_id": object_id, "store_id": STORE_ID},
                {"$pull": {"pets": pet_name}}
            )
            pet_types_collection.update_one(
                {"_id": object_id, "store_id": STORE_ID},
                {"$push": {"pets": new_name}}
            )

        # Create response object
        updated_pet = {
            "name": new_name,
            "birthdate": birthdate,
            "picture": picture_filename
        }

        return jsonify(updated_pet), 200
    except Exception as e:
        return jsonify({"error": "Database error"}), 500

@app.route('/kill', methods=['GET'])
def kill_container():
    os._exit(1)

@app.route("/pictures/<filename>", methods=["GET"])
def get_picture(filename):
    file_path = os.path.join(IMAGE_DIR, filename)
    
    if not os.path.exists(file_path):
        return jsonify({"error": "Not found"}), 404
    
    # Determine MIME type based on file extension
    _, ext = os.path.splitext(filename)
    if ext.lower() in ['.jpg', '.jpeg']:
        mimetype = 'image/jpg'
    elif ext.lower() == '.png':
        mimetype = 'image/png'
    else:
        mimetype = 'application/octet-stream'
    
    return send_file(file_path, mimetype=mimetype)

# Entry point for running the Flask server
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001)