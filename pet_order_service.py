from flask import Flask, jsonify, request
import requests
import os
import uuid
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure
import random

app = Flask(__name__)

# MongoDB connection
MONGO_URI = os.getenv("MONGO_URI", "mongodb://mongodb:27017/")
client = MongoClient(MONGO_URI)
db = client.transactions
transactions_collection = db.transactions

# Pet store service URLs
PET_STORE_1_URL = os.getenv("PET_STORE_1_URL", "http://pet-store1:5001")
PET_STORE_2_URL = os.getenv("PET_STORE_2_URL", "http://pet-store2:5001")

@app.route("/", methods=["GET"])
def home():
    return jsonify({"message": "Pet Order API is running"}), 200

def get_pet_type_id(pet_type_name, store_url):
    """Get pet type ID from a pet store by name"""
    try:
        response = requests.get(f"{store_url}/pet-types")
        if response.status_code == 200:
            pet_types = response.json()
            for pet_type in pet_types:
                if pet_type["type"].lower() == pet_type_name.lower():
                    return pet_type["id"]
        return None
    except:
        return None

def get_pets_of_type(pet_type_id, store_url):
    """Get all pets of a specific type from a store"""
    try:
        response = requests.get(f"{store_url}/pet-types/{pet_type_id}/pets")
        if response.status_code == 200:
            return response.json()
        return []
    except:
        return []

def delete_pet_from_store(pet_type_id, pet_name, store_url):
    """Delete a pet from a store"""
    try:
        response = requests.delete(f"{store_url}/pet-types/{pet_type_id}/pets/{pet_name}")
        return response.status_code == 204
    except:
        return False

def find_available_pet(pet_type, store=None, pet_name=None):
    """Find an available pet according to the assignment rules"""
    store_urls = {1: PET_STORE_1_URL, 2: PET_STORE_2_URL}
    
    if store and pet_name:
        # Case 1: specific store and pet name
        store_url = store_urls.get(store)
        if not store_url:
            return None
            
        pet_type_id = get_pet_type_id(pet_type, store_url)
        if not pet_type_id:
            return None
            
        pets = get_pets_of_type(pet_type_id, store_url)
        for pet in pets:
            if pet["name"] == pet_name:
                return {"pet": pet, "store": store, "pet_type_id": pet_type_id, "store_url": store_url}
        return None
    
    elif store and not pet_name:
        # Case 2: specific store, any pet
        store_url = store_urls.get(store)
        if not store_url:
            return None
            
        pet_type_id = get_pet_type_id(pet_type, store_url)
        if not pet_type_id:
            return None
            
        pets = get_pets_of_type(pet_type_id, store_url)
        if pets:
            chosen_pet = random.choice(pets)
            return {"pet": chosen_pet, "store": store, "pet_type_id": pet_type_id, "store_url": store_url}
        return None
    
    else:
        # Case 3: any store, any pet
        available_pets = []
        
        for store_id, store_url in store_urls.items():
            pet_type_id = get_pet_type_id(pet_type, store_url)
            if pet_type_id:
                pets = get_pets_of_type(pet_type_id, store_url)
                for pet in pets:
                    available_pets.append({
                        "pet": pet, 
                        "store": store_id, 
                        "pet_type_id": pet_type_id, 
                        "store_url": store_url
                    })
        
        if available_pets:
            return random.choice(available_pets)
        return None

@app.route("/purchases", methods=["POST"])
def post_purchase():
    try:
        if not request.is_json:
            return jsonify({"error": "Expected application/json media type"}), 415

        data = request.get_json(silent=True)
        if data is None:
            return jsonify({"error": "Malformed data"}), 400

        # Validate required fields
        if "purchaser" not in data or not isinstance(data["purchaser"], str):
            return jsonify({"error": "Malformed data"}), 400
        if "pet-type" not in data or not isinstance(data["pet-type"], str):
            return jsonify({"error": "Malformed data"}), 400

        purchaser = data["purchaser"].strip()
        pet_type = data["pet-type"].strip()
        store = data.get("store")
        pet_name = data.get("pet-name")

        if store is not None and not isinstance(store, int):
            return jsonify({"error": "Malformed data"}), 400
        if pet_name is not None and not isinstance(pet_name, str):
            return jsonify({"error": "Malformed data"}), 400

        # Validate store is 1 or 2
        if store is not None and store not in [1, 2]:
            return jsonify({"error": "Malformed data"}), 400

        # pet-name can only be supplied if store is supplied
        if pet_name and store is None:
            return jsonify({"error": "Malformed data"}), 400

        # Find available pet
        result = find_available_pet(pet_type, store, pet_name)
        if not result:
            return jsonify({"error": "No pet of this type is available"}), 400

        # Delete pet from store
        if not delete_pet_from_store(result["pet_type_id"], result["pet"]["name"], result["store_url"]):
            return jsonify({"error": "Failed to remove pet from store"}), 500

        # Generate purchase ID
        purchase_id = str(uuid.uuid4())

        # Create transaction record
        transaction = {
            "purchaser": purchaser,
            "pet-type": pet_type,
            "store": result["store"],
            "purchase-id": purchase_id
        }

        # Save transaction to database
        transactions_collection.insert_one(transaction)

        # Create purchase response
        purchase = {
            "purchaser": purchaser,
            "pet-type": pet_type,
            "store": result["store"],
            "pet-name": result["pet"]["name"],
            "purchase-id": purchase_id
        }

        return jsonify(purchase), 201

    except Exception as e:
        return jsonify({"error": "Server error"}), 500

@app.route("/transactions", methods=["GET"])
def get_transactions():
    try:
        # Check authorization header
        owner_header = request.headers.get("OwnerPC")
        if owner_header != "LovesPetsL2M3n4":
            return jsonify({"error": "Unauthorized"}), 401

        # Build query from query parameters
        query = {}
        for key, value in request.args.items():
            if key in ["purchaser", "pet-type", "store", "purchase-id"]:
                if key == "store":
                    try:
                        query[key] = int(value)
                    except ValueError:
                        query[key] = value
                else:
                    query[key] = value

        # Get transactions from database
        transactions = list(transactions_collection.find(query, {"_id": 0}))
        return jsonify(transactions), 200

    except Exception as e:
        return jsonify({"error": "Server error"}), 500

@app.route('/kill', methods=['GET'])
def kill_container():
    os._exit(1)

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5003))
    app.run(host="0.0.0.0", port=port)