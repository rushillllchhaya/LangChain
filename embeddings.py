from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain.evaluation import load_evaluator
from dotenv import load_dotenv
import os

load_dotenv()

def main():
    embedding_function = GoogleGenerativeAIEmbeddings(
        model="models/embedding-001",
        google_api_key=os.getenv("GEMINI_API_KEY")
    )
    vector = embedding_function.embed_query("apple")
    print(f"Vector for 'apple' : {vector}")
    print(f"Vector length : {len(vector)}")

    evaluator = load_evaluator(
        "pairwise_embedding_distance",
        embeddings=embedding_function  # <-- Pass your Gemini embedding function here
    )
    words = ("iphone", "apple")
    x = evaluator.evaluate_string_pairs(prediction=words[0], prediction_b=words[1])
    print(f"Comparing ({words[0]}, {words[1]}): {x}")

if __name__ == "__main__":
    main()