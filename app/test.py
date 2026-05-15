from dotenv import load_dotenv
import os
load_dotenv()

print(os.getenv("DATABASE_URL"))
print(type(os.getenv("DATABASE_URL")))