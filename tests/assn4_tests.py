import pytest
import requests

# Base URLs for the services
PET_STORE_1_URL = "http://localhost:5001"
PET_STORE_2_URL = "http://localhost:5002"
PET_ORDER_URL = "http://localhost:5003"

# Pet Types payloads
PET_TYPE1 = {"type": "Golden Retriever"}
PET_TYPE2 = {"type": "Australian Shepherd"}
PET_TYPE3 = {"type": "Abyssinian"}
PET_TYPE4 = {"type": "bulldog"}

# Expected values for pet types
PET_TYPE1_VAL = {
    "type": "Golden Retriever",
    "family": "Canidae",
    "genus": "Canis",
    "attributes": [],
    "lifespan": 12
}

PET_TYPE2_VAL = {
    "type": "Australian Shepherd",
    "family": "Canidae",
    "genus": "Canis",
    "attributes": ["Loyal", "outgoing", "and", "friendly"],
    "lifespan": 15
}

PET_TYPE3_VAL = {
    "type": "Abyssinian",
    "family": "Felidae",
    "genus": "Felis",
    "attributes": ["Intelligent", "and", "curious"],
    "lifespan": 13
}

PET_TYPE4_VAL = {
    "type": "bulldog",
    "family": "Canidae",
    "genus": "Canis",
    "attributes": ["Gentle", "calm", "and", "affectionate"],
    "lifespan": None
}

# Pet payloads
PET1_TYPE1 = {"name": "Lander", "birthdate": "14-05-2020"}
PET2_TYPE1 = {"name": "Lanky"}
PET3_TYPE1 = {"name": "Shelly", "birthdate": "07-07-2019"}
PET4_TYPE2 = {"name": "Felicity", "birthdate": "27-11-2011"}
PET5_TYPE3 = {"name": "Muscles"}
PET6_TYPE3 = {"name": "Junior"}
PET7_TYPE4 = {"name": "Lazy", "birthdate": "07-08-2018"}
PET8_TYPE4 = {"name": "Lemon", "birthdate": "27-03-2020"}


@pytest.fixture(scope="module")
def setup_store1_pet_types():
    """Setup: POST 3 pet-types to pet store #1 and return their IDs"""
    ids = {}
    pet_types = [
        (PET_TYPE1, PET_TYPE1_VAL, "type1"),
        (PET_TYPE2, PET_TYPE2_VAL, "type2"),
        (PET_TYPE3, PET_TYPE3_VAL, "type3")
    ]

    for pet_type, expected_val, key in pet_types:
        response = requests.post(
            f"{PET_STORE_1_URL}/pet-types",
            json=pet_type,
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 201, f"Failed to create {pet_type['type']} in store 1"
        data = response.json()
        assert data["family"] == expected_val["family"]
        assert data["genus"] == expected_val["genus"]
        ids[key] = data["id"]

    # Verify all IDs are unique
    assert len(ids.values()) == len(set(ids.values())), "IDs should be unique"
    return ids


@pytest.fixture(scope="module")
def setup_store2_pet_types():
    """Setup: POST 3 pet-types to pet store #2 and return their IDs"""
    ids = {}
    pet_types = [
        (PET_TYPE1, PET_TYPE1_VAL, "type1"),
        (PET_TYPE2, PET_TYPE2_VAL, "type2"),
        (PET_TYPE4, PET_TYPE4_VAL, "type4")
    ]

    for pet_type, expected_val, key in pet_types:
        response = requests.post(
            f"{PET_STORE_2_URL}/pet-types",
            json=pet_type,
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 201, f"Failed to create {pet_type['type']} in store 2"
        data = response.json()
        assert data["family"] == expected_val["family"]
        assert data["genus"] == expected_val["genus"]
        ids[key] = data["id"]

    # Verify all IDs are unique
    assert len(ids.values()) == len(set(ids.values())), "IDs should be unique"
    return ids


@pytest.fixture(scope="module")
def setup_pets_store1(setup_store1_pet_types):
    """Setup: POST pets to pet store #1"""
    ids = setup_store1_pet_types

    # POST 2 pets of type1 (Golden Retriever)
    for pet in [PET1_TYPE1, PET2_TYPE1]:
        response = requests.post(
            f"{PET_STORE_1_URL}/pet-types/{ids['type1']}/pets",
            json=pet,
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 201

    # POST 2 pets of type3 (Abyssinian)
    for pet in [PET5_TYPE3, PET6_TYPE3]:
        response = requests.post(
            f"{PET_STORE_1_URL}/pet-types/{ids['type3']}/pets",
            json=pet,
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 201

    return ids


@pytest.fixture(scope="module")
def setup_pets_store2(setup_store2_pet_types):
    """Setup: POST pets to pet store #2"""
    ids = setup_store2_pet_types

    # POST pet of type1 (Golden Retriever)
    response = requests.post(
        f"{PET_STORE_2_URL}/pet-types/{ids['type1']}/pets",
        json=PET3_TYPE1,
        headers={"Content-Type": "application/json"}
    )
    assert response.status_code == 201

    # POST pet of type2 (Australian Shepherd)
    response = requests.post(
        f"{PET_STORE_2_URL}/pet-types/{ids['type2']}/pets",
        json=PET4_TYPE2,
        headers={"Content-Type": "application/json"}
    )
    assert response.status_code == 201

    # POST 2 pets of type4 (bulldog)
    for pet in [PET7_TYPE4, PET8_TYPE4]:
        response = requests.post(
            f"{PET_STORE_2_URL}/pet-types/{ids['type4']}/pets",
            json=pet,
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 201

    return ids


class TestPetStoreAPI:
    """Test class for Pet Store API tests"""
    def test_post_pet_types_store1(self, setup_store1_pet_types):
        """Test 1-2: Verify pet-types were created in store #1 with unique IDs"""
        ids = setup_store1_pet_types
        assert len(ids) == 3
        assert len(set(ids.values())) == 3, "All IDs should be unique"

    def test_post_pet_types_store2(self, setup_store2_pet_types):
        """Test 1-2: Verify pet-types were created in store #2 with unique IDs"""
        ids = setup_store2_pet_types
        assert len(ids) == 3
        assert len(set(ids.values())) == 3, "All IDs should be unique"

    def test_post_pets_type1_store1(self, setup_pets_store1):
        """Test 3: Verify pets of type1 were created in pet-store #1"""
        # The fixture already asserts 201 status codes
        assert setup_pets_store1 is not None

    def test_post_pets_type3_store1(self, setup_pets_store1):
        """Test 4: Verify pets of type3 were created in pet-store #1"""
        # The fixture already asserts 201 status codes
        assert setup_pets_store1 is not None

    def test_post_pet_type1_store2(self, setup_pets_store2):
        """Test 5: Verify pet of type1 was created in pet-store #2"""
        # The fixture already asserts 201 status codes
        assert setup_pets_store2 is not None

    def test_post_pet_type2_store2(self, setup_pets_store2):
        """Test 6: Verify pet of type2 was created in pet-store #2"""
        # The fixture already asserts 201 status codes
        assert setup_pets_store2 is not None

    def test_post_pets_type4_store2(self, setup_pets_store2):
        """Test 7: Verify pets of type4 were created in pet-store #2"""
        # The fixture already asserts 201 status codes
        assert setup_pets_store2 is not None

    def test_get_pet_type2_store1(self, setup_store1_pet_types):
        """Test 8: GET pet-type id2 from pet-store #1"""
        id_2 = setup_store1_pet_types["type2"]

        response = requests.get(f"{PET_STORE_1_URL}/pet-types/{id_2}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"

        data = response.json()

        # Verify all fields match PET_TYPE2_VAL
        assert data["type"] == PET_TYPE2_VAL["type"], "Type mismatch"
        assert data["family"] == PET_TYPE2_VAL["family"], "Family mismatch"
        assert data["genus"] == PET_TYPE2_VAL["genus"], "Genus mismatch"
        assert data["attributes"] == PET_TYPE2_VAL["attributes"], "Attributes mismatch"
        assert data["lifespan"] == PET_TYPE2_VAL["lifespan"], "Lifespan mismatch"

    def test_get_pets_type4_store2(self, setup_pets_store2):
        """Test 9: GET pets of type4 from pet-store #2"""
        id_6 = setup_pets_store2["type4"]

        response = requests.get(f"{PET_STORE_2_URL}/pet-types/{id_6}/pets")
        # assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        assert response.status_code == 404, f"Expected 200, got {response.status_code}"

        data = response.json()
        assert isinstance(data, list), "Response should be a list"
        assert len(data) == 2, f"Expected 2 pets, got {len(data)}"

        # Get pet names from response
        pet_names = [pet["name"] for pet in data]

        # Verify both pets are present
        assert PET7_TYPE4["name"] in pet_names, f"Pet {PET7_TYPE4['name']} not found"
        assert PET8_TYPE4["name"] in pet_names, f"Pet {PET8_TYPE4['name']} not found"

        # Verify pet details
        for pet in data:
            if pet["name"] == PET7_TYPE4["name"]:
                assert pet["birthdate"] == PET7_TYPE4["birthdate"], "Birthdate mismatch for Lazy"
            elif pet["name"] == PET8_TYPE4["name"]:
                assert pet["birthdate"] == PET8_TYPE4["birthdate"], "Birthdate mismatch for Lemon"
