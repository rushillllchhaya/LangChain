import argparse
import os
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_community.vectorstores import Chroma
from langchain.prompts import ChatPromptTemplate
from langchain_groq import ChatGroq


from dotenv import load_dotenv
load_dotenv()

CHROMA_DB_PATH = "chroma_db"

PROMPT_TEMPLATE = """
You are a helpful assistant. Use the following context to answer the user's question.

Context:
{context}

Question:
{question}
"""

def main():
    parser = argparse.ArgumentParser(description="Query the Chroma database with Gemini.")
    parser.add_argument("query", type=str, help="Your Query")
    args = parser.parse_args()
    query = args.query

    embedding_function = GoogleGenerativeAIEmbeddings(
        model="models/embedding-001",
        google_api_key=os.getenv("GEMINI_API_KEY")
    )

    db = Chroma(persist_directory=CHROMA_DB_PATH, embedding_function=embedding_function)
    results = db.similarity_search_with_relevance_scores(query, k=3)

    if len(results) == 0:
        print("Unable to find Relevance")
        return

    context_text = "\n\n---\n\n".join([doc.page_content for doc, _score in results])
    prompt_template = ChatPromptTemplate.from_template(PROMPT_TEMPLATE)
    prompt = prompt_template.format(context=context_text, question=query)

    # Use ChatGoogleGenerativeAI for text generation
    llm = ChatGroq(
        groq_api_key=os.getenv("GROQ_API_KEY"),
        model_name="llama3-70b-8192"  # You can change to another supported model if needed
    )
    response = llm.invoke(prompt)

    sources = [doc.metadata.get("source", None) for doc, _score in results]
    formatted_response = f"Response: {response.content}\nSources: {sources}"
    print(formatted_response)

if __name__ == "__main__":
    main()