"""Run this once to create the sample PDF for the demo."""
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch

doc = SimpleDocTemplate(
    "sample-docs/rag-explained.pdf",
    pagesize=letter,
    rightMargin=inch,
    leftMargin=inch,
    topMargin=inch,
    bottomMargin=inch,
)

styles = getSampleStyleSheet()
heading = ParagraphStyle("heading", parent=styles["Heading1"], spaceAfter=12)
body = styles["BodyText"]
body.spaceAfter = 10

content = []

def h(text):
    content.append(Paragraph(text, heading))

def p(text):
    content.append(Paragraph(text, body))
    content.append(Spacer(1, 6))

h("RAG: Retrieval-Augmented Generation — The Plain English Guide")
p("This guide explains RAG in plain English with real examples. It was created for The AI Stackk YouTube channel.")

h("What is RAG?")
p("RAG stands for Retrieval-Augmented Generation. It is a technique that lets an AI model answer questions using your own private documents, not just its training data.")
p("Think of it like hiring a new employee. On their first day, they know a lot about the world — but they have never read your company handbook. RAG is the handbook.")

h("How Does RAG Work?")
p("RAG works in three steps. First, your documents are split into small chunks of text. Second, when you ask a question, the system finds the chunks most relevant to your question. Third, those chunks are handed to the AI, which reads them and generates an answer.")
p("The key insight: the AI only reads the relevant chunks, not the whole document. This keeps responses fast and accurate.")

h("When Should You Use RAG?")
p("Use RAG when you have private documents the AI has never seen. Examples: company policy documents, product manuals, legal contracts, research papers, your own notes, or customer support FAQs.")
p("RAG is ideal when you need answers grounded in a specific source, and when you need to be able to point to exactly where the answer came from.")

h("When Should You NOT Use RAG?")
p("Do not use RAG when your question is general knowledge that any AI already knows. Asking a RAG system 'what is the capital of France?' is wasteful — just ask the AI directly.")
p("Also avoid RAG when your documents are very short. If your entire knowledge base is one page, just paste it into the prompt directly. RAG adds value at scale — hundreds of pages or more.")
p("RAG also struggles with math-heavy or table-heavy documents. If your doc is mostly spreadsheets and formulas, RAG chunking will lose the structure. Use a specialized table-parsing approach instead.")

h("Real Example: Customer Support Bot")
p("Imagine you run an AI tool company. Your support team answers the same 50 questions every day. You build a RAG system: upload your FAQ document, connect it to Claude, and let customers ask questions directly.")
p("Without RAG: the AI makes up answers or says it does not know. With RAG: the AI finds the exact FAQ entry, quotes it, and answers accurately. Your support team only handles the edge cases.")

h("What Makes a Good RAG Document?")
p("Good RAG documents are well-structured with clear headings. Each section covers one topic. Sentences are complete and self-contained — because chunks may be shown to the AI without surrounding context.")
p("Bad RAG documents are dense spreadsheets, scanned images with no text layer, or documents with heavy cross-references like 'see section 4.2.1 above.'")

h("The AI Stackk — Safe Usage Note")
p("RAG keeps your data local. Your documents are embedded on your machine and stored in a local vector database. They are never sent to the AI provider during indexing — only the retrieved chunks are sent at query time, and only the text you explicitly ask about.")
p("This makes RAG one of the safest ways to use AI with sensitive company documents.")

doc.build(content)
print("Sample PDF created: sample-docs/rag-explained.pdf")
