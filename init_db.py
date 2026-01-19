from database import Base, engine
import os

if __name__ == "__main__":
    print(f"Connecting to: {os.getenv('DATABASE_URL')}")
    if engine:
        print("Creating tables...")
        Base.metadata.create_all(bind=engine)
        print("Tables created successfully.")
    else:
        print("No DATABASE_URL found. Please set it in your environment.")
