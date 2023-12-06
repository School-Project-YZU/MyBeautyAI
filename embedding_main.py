from flask import Flask, render_template, request, jsonify
import os
from langchain.text_splitter import CharacterTextSplitter
from langchain.embeddings.openai import OpenAIEmbeddings
from langchain.vectorstores import FAISS
from langchain.chains.question_answering import load_qa_chain
from langchain.callbacks import get_openai_callback
from langchain.chat_models import ChatOpenAI
from PyPDF2 import PdfReader
from docx import Document

app = Flask(__name__)

chat_history = []

def get_text_from_pdf(pdf_path):
    text = ""
    with open(pdf_path, 'rb') as file:
        pdf_reader = PdfReader(file)
        for page in pdf_reader.pages:
            text += page.extract_text()
    return text

def get_text_from_docx(docx_path):
    doc = Document(docx_path)
    text = ""
    for paragraph in doc.paragraphs:
        text += paragraph.text + "\n"
    return text

@app.route('/')
def index():
    return render_template('index.html', chat_history=chat_history)

@app.route('/get_response', methods=['POST'])
def get_response():
    user_input = request.form.get('user_input')
    if user_input:
        files_folder = 'data'

        text = ""
        for filename in os.listdir(files_folder):
            file_path = os.path.join(files_folder, filename)
            if filename.endswith('.pdf'):
                text += get_text_from_pdf(file_path)
            elif filename.endswith('.docx'):
                text += get_text_from_docx(file_path)

        text_splitter = CharacterTextSplitter(
            separator="\n",
            chunk_size=1000,
            chunk_overlap=200,
            length_function=len
        )
        chunks = text_splitter.split_text(text)

        embeddings = OpenAIEmbeddings()
        knowledge_base = FAISS.from_texts(chunks, embeddings)

        docs = knowledge_base.similarity_search(user_input)

        llm = ChatOpenAI(
            model_name="gpt-4-1106-preview",
            temperature=0.4
        )

        chain = load_qa_chain(llm, chain_type="stuff")

        with get_openai_callback() as cb:
            response = chain.run(input_documents=docs, question=user_input)

        response = {'response': response}

        chat_history.append({'user': user_input, 'assistant': response['response']})

        return jsonify(response)

if __name__ == '__main__':
    app.run(debug=True)
