# RAGucation - Textbook Q&A (Local, Offline)

Ask your textbooks anything — privately, locally, and with citations.
ScholarRAG is a lightweight Retrieval-Augmented Generation (RAG) system that indexes textbooks (PDFs) and answers questions using a local LLM. 
Built with Streamlit, ChromaDB, and Ollama, it runs fully offline

## Features
	•	Upload textbooks (PDFs) → automatic parsing, chunking, and embedding.
	•	Semantic retrieval → finds the most relevant passages from your library.
	•	Cited answers → LLM answers with inline references [1], [2] to textbook pages.
	•	Local-first → no external API calls; all processing on-device.
	•	Streamlit UI → simple, interactive web app for study or research.



Demo Screenshot

<img src="screenshot.png" width="800">



###  Tech Stack
	•	Frontend / UI: Streamlit
	•	Vector Store: ChromaDB
	•	Embeddings: SentenceTransformers (MiniLM)
	•	LLM Runtime: Ollama with llama3.1:8b-instruct
	•	Parsing: pypdf


intallation 

Clone & Install
git clone https://github.com/your-username/scholarrag.git
cd scholarrag
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt


Install Ollama & Pull a Model
ollama pull llama3.1:8b-instruct


streamlit run app.py



Usage
	1.	Upload one or more PDF textbooks via the sidebar.
	2.	Click Index PDFs → text is chunked, embedded, and stored.
	3.	Ask a question in the main box.
	4.	See:
	•	Retrieved context passages.
	•	AI-generated answer with citations to pages.


