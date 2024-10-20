from pymongo import MongoClient
from werkzeug.security import generate_password_hash

# MongoDB Configuration
client = MongoClient("mongodb+srv://jharshit61:New1212@cluster0.sydzy.mongodb.net/developerportal?retryWrites=true&w=majority")
db = client["developerportal"]
users_collection = db["users"]

# Fetch all users
users = users_collection.find()

# Loop through each user and hash the password if it's in plaintext
for user in users:
    password = user.get('password')  # Get the plaintext password
    
    # Check if the password is already hashed (just a simple check for the presence of 'pbkdf2')
    if not password.startswith('pbkdf2:sha256:'):
        # Hash the plaintext password
        hashed_password = generate_password_hash(password, method='pbkdf2:sha256', salt_length=16)
        
        # Update the user with the hashed password
        users_collection.update_one(
            {"_id": user["_id"]},  # Match by user ID
            {"$set": {"password": hashed_password}}  # Update the password field
        )
        print(f"Password for user {user['email']} has been hashed and updated.")
    else:
        print(f"Password for user {user['email']} is already hashed.")

print("All users' passwords have been processed.")
