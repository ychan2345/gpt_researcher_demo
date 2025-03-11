import os
import streamlit as st
from gpt_researcher.config import Config
import asyncio
from gpt_researcher import GPTResearcher
from enum import Enum
import json
import tempfile
import shutil
import logging
import subprocess
import sys
from gpt_researcher.utils.enum import ReportType, ReportSource
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Verify API keys are loaded
if not os.getenv("OPENAI_API_KEY"):
    st.error("OPENAI_API_KEY not found in environment variables. Please make sure it's set in your .env file.")
    st.stop()

if not os.getenv("TAVILY_API_KEY"):
    st.warning("TAVILY_API_KEY not found in environment variables. Some search functionality may be limited.")

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Set page configuration
st.set_page_config(
    page_title="GPT Researcher",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Define report types and sources matching the HTML form
class ToneOptions(str, Enum):
    OBJECTIVE = "Objective"
    FORMAL = "Formal"
    ANALYTICAL = "Analytical"
    PERSUASIVE = "Persuasive"
    INFORMATIVE = "Informative"
    EXPLANATORY = "Explanatory"
    DESCRIPTIVE = "Descriptive"
    CRITICAL = "Critical"
    COMPARATIVE = "Comparative"
    SPECULATIVE = "Speculative"
    REFLECTIVE = "Reflective"
    NARRATIVE = "Narrative"
    HUMOROUS = "Humorous"
    OPTIMISTIC = "Optimistic"
    PESSIMISTIC = "Pessimistic"

# Set up session state for storing research results
if "research_result" not in st.session_state:
    st.session_state.research_result = None
if "task_id" not in st.session_state:
    st.session_state.task_id = None

# Main title
st.title("GPT Researcher 🔍")

# Create a form for user input
with st.form("research_form"):
    st.subheader("Research Parameters")

    # Research question input
    query = st.text_input("What would you like me to research?", placeholder="Enter your research question here")

    # Report type dropdown using exact values from HTML
    col1, col2 = st.columns(2)

    with col1:
        report_type = st.selectbox(
            "What type of report would you like me to generate?",
            options=[
                "research_report",
                "detailed_report",
                "resource_report"
            ],
            format_func=lambda x: {
                "research_report": "Summary - Short and fast (~2 min)",
                "detailed_report": "Detailed - In depth and longer (~5 min)",
                "resource_report": "Resource Report"
            }.get(x, x)
        )

        # Report source dropdown using exact values from HTML
        report_source = st.selectbox(
            "What sources would you like me to research from?",
            options=[
                "web",
                "local",
                "hybrid",
                "deep",
                "azure"
            ],
            format_func=lambda x: {
                "web": "The Web",
                "local": "My Documents",
                "hybrid": "Hybrid",
                "deep": "Deep Research",
                "azure": "Azure storage"
            }.get(x, x)
        )

    with col2:
        # Tone dropdown using exact values from HTML
        tone = st.selectbox(
            "In which tone would you like the report to be generated?",
            options=[
                "Objective",
                "Formal",
                "Analytical",
                "Persuasive",
                "Informative",
                "Explanatory",
                "Descriptive",
                "Critical",
                "Comparative",
                "Speculative",
                "Reflective",
                "Narrative",
                "Humorous",
                "Optimistic",
                "Pessimistic"
            ],
            format_func=lambda x: {
                "Objective": "Objective - Impartial and unbiased presentation of facts and findings",
                "Formal": "Formal - Adheres to academic standards with sophisticated language and structure",
                "Analytical": "Analytical - Critical evaluation and detailed examination of data and theories",
                "Persuasive": "Persuasive - Convincing the audience of a particular viewpoint or argument",
                "Informative": "Informative - Providing clear and comprehensive information on a topic",
                "Explanatory": "Explanatory - Clarifying complex concepts and processes",
                "Descriptive": "Descriptive - Detailed depiction of phenomena, experiments, or case studies",
                "Critical": "Critical - Judging the validity and relevance of the research and its conclusions",
                "Comparative": "Comparative - Juxtaposing different theories, data, or methods to highlight differences and similarities",
                "Speculative": "Speculative - Exploring hypotheses and potential implications or future research directions",
                "Reflective": "Reflective - Considering the research process and personal insights or experiences",
                "Narrative": "Narrative - Telling a story to illustrate research findings or methodologies",
                "Humorous": "Humorous - Light-hearted and engaging, usually to make the content more relatable",
                "Optimistic": "Optimistic - Highlighting positive findings and potential benefits",
                "Pessimistic": "Pessimistic - Focusing on limitations, challenges, or negative outcomes"
            }.get(x, x)
        )

    # Document section for local and hybrid sources
    if report_source in ["local", "hybrid"]:
        st.subheader("Documents")

        # Display existing documents from my-docs folder
        my_docs_path = "my-docs"
        st.write("Documents available for research:")
        if os.path.exists(my_docs_path) and os.path.isdir(my_docs_path):
            docs_files = os.listdir(my_docs_path)
            if docs_files:
                for file in docs_files:
                    st.write(f"- {file}")
            else:
                st.write("No documents found in my-docs folder.")
        else:
            st.write("my-docs folder not found.")

    # Submit button
    submit_button = st.form_submit_button("Start Research")

# Process the research request when submitted
if submit_button and query:
    # Reset the summary result when starting a new research
    if "summary_result" in st.session_state:
        st.session_state.summary_result = None
        
    with st.spinner("Researching... This may take a few minutes."):
        try:
            # Create configuration
            cfg = Config()

            # Set up document paths for research
            doc_paths = []
            if report_source in ["local", "hybrid"]:
                # Use the my-docs folder directly
                my_docs_path = "my-docs"
                if os.path.exists(my_docs_path) and os.path.isdir(my_docs_path):
                    docs_files = [os.path.join(my_docs_path, f) for f in os.listdir(my_docs_path)]
                    if docs_files:
                        # Convert DOCX files to text without requiring extra packages
                        st.info("Processing document files...")

                        # Log the found documents
                        for file_name in docs_files:
                            st.info(f"Including document: {file_name}")

                            # For DOCX files, extract content using a simple approach
                            if file_name.lower().endswith('.docx'):
                                try:
                                    # Create a simple text extraction function
                                    def extract_text_from_docx(docx_path):
                                        try:
                                            # Try a basic ZIP extraction since DOCX is a ZIP file
                                            import zipfile
                                            import xml.etree.ElementTree as ET
                                            import re

                                            text_content = []

                                            with zipfile.ZipFile(docx_path) as docx_zip:
                                                # Look for document.xml which contains the main content
                                                if 'word/document.xml' in docx_zip.namelist():
                                                    content = docx_zip.read('word/document.xml').decode('utf-8')
                                                    # Simple regex to extract text between <w:t> tags
                                                    matches = re.findall(r'<w:t[^>]*>(.*?)</w:t>', content)
                                                    if matches:
                                                        text_content = ' '.join(matches)
                                                    else:
                                                        # Fallback: just extract any readable text
                                                        for file_info in docx_zip.infolist():
                                                            if file_info.filename.endswith('.xml'):
                                                                try:
                                                                    file_content = docx_zip.read(file_info.filename).decode('utf-8')
                                                                    # Extract text between any XML tags
                                                                    text = re.sub(r'<[^>]+>', ' ', file_content)
                                                                    text = re.sub(r'\s+', ' ', text).strip()
                                                                    if text:
                                                                        text_content.append(text)
                                                                except:
                                                                    pass

                                            return '\n'.join(text_content) if isinstance(text_content, list) else text_content
                                        except Exception as e:
                                            # If all extraction methods fail, return file content as plain text
                                            try:
                                                with open(docx_path, 'r', errors='ignore') as f:
                                                    return f.read()
                                            except:
                                                return f"Error extracting text: {str(e)}"

                                    docx_path = file_name
                                    text_content = extract_text_from_docx(docx_path)

                                    # Save as text file alongside the original
                                    text_file_path = os.path.join(my_docs_path, os.path.splitext(os.path.basename(file_name))[0] + '.txt')
                                    with open(text_file_path, 'w', encoding='utf-8') as f:
                                        f.write(text_content)
                                    doc_paths.append(text_file_path)
                                    st.info(f"Created text backup of {file_name}")
                                except Exception as e:
                                    st.warning(f"Could not process {file_name}: {str(e)}")
                                    # Try a very basic approach - just copy the file with .txt extension
                                    try:
                                        docx_path = file_name
                                        text_file_path = os.path.join(my_docs_path, os.path.splitext(os.path.basename(file_name))[0] + '.txt')
                                        with open(docx_path, 'rb') as source_file:
                                            with open(text_file_path, 'w', encoding='utf-8', errors='ignore') as target_file:
                                                # Try to extract data table from DOCX as plain text
                                                content = source_file.read().decode('utf-8', errors='ignore')
                                                target_file.write(content)
                                        doc_paths.append(text_file_path)
                                        st.info(f"Created basic text backup of {file_name}")
                                    except Exception as inner_e:
                                        st.error(f"All extraction methods failed for {file_name}: {str(inner_e)}")

                    # Set the document path for local and hybrid research
                    #os.environ["DOC_PATH"] = os.path.abspath(my_docs_path) # No longer needed, using doc_paths directly
                    logging.info(f"Document paths set to: {doc_paths}")

                else:
                    st.warning("my-docs folder not found. Please create it and add your documents.")

            # Create a unique task ID without relying on event loop
            import time
            task_id = f"streamlit_task_{int(time.time())}"
            st.session_state.task_id = task_id

            # Initialize researcher with the query
            researcher = GPTResearcher(
                query=query,
                report_type=report_type,
                report_source=report_source,
                tone=tone,
                config_path=None,
                websocket=None,
                document_urls=doc_paths if report_source == "web" else None  # Use document_urls parameter
            )
            
            # If using local docs in a non-web source, set the config doc_path
            if report_source in ["local", "hybrid", "deep"] and doc_paths:
                researcher.cfg.doc_path = "my-docs"

            # Use asyncio.run which creates its own event loop
            async def run_research():
                # First conduct the research
                await researcher.conduct_research()
                # Then generate the report based on the research
                report = await researcher.write_report()
                return report

            report = asyncio.run(run_research())


            # Store result in session state
            st.session_state.research_result = report

            # No temporary directory to clean up since we're using my-docs directly

        except Exception as e:
            st.error(f"An error occurred during research: {str(e)}")
            logger.error(f"Research error: {str(e)}", exc_info=True)

# Display research results if available
if st.session_state.research_result:
    st.subheader("Research Results")

    # Initialize summary state if not exists
    if "summary_result" not in st.session_state:
        st.session_state.summary_result = None

    # Generate summary automatically when results are available
    if st.session_state.summary_result is None:
        with st.spinner("Generating summary automatically..."):
            try:
                # Create a summarization function that uses OpenAI to summarize the report
                async def summarize_report(content):
                    # Use OpenAI to summarize the content
                    import openai
                    import os

                    client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
                    # Explicitly set model to GPT-4o to ensure it's always used
                    model = "gpt-4o"
                    st.info(f"Using {model} for summarization")
                    
                    # Determine if this is a hybrid research report
                    is_hybrid = report_source == "hybrid"
                    is_local = report_source == "local"
                    has_local_docs = is_hybrid or is_local
                    
                    # Custom instructions based on research type
                    doc_instruction = ""
                    if has_local_docs:
                        doc_instruction = (
                            "LOCAL DOCUMENT EMPHASIS: This research includes local documents about Dr. Brooks Dian and PCIOL usage data. "
                            "You MUST prominently include a section in your summary specifically highlighting data from these local documents. "
                            "Extract and emphasize all PCIOL volume data, dates, probabilities, and other numerical values from the local documents. "
                            "This information is critical and must be presented clearly in your summary."
                        )
                    
                    system_message = (
                        "You are a professional research summarizer specializing in comprehensive reports. "
                        "Your task is to create a clear, accurate summary that captures all key information. "
                        f"This report was generated using {'hybrid (web + local documents)' if is_hybrid else report_source} research mode. "
                        f"{doc_instruction}"
                    )
                    
                    user_message = (
                        "Please summarize the following research report carefully and thoroughly. "
                        f"{'IMPORTANT: This report contains information from local documents about Dr. Brooks Dian and PCIOL data. Specifically extract and highlight ALL numerical data related to PCIOL volumes, probabilities, and historical trends from these documents.' if has_local_docs else ''} "
                        "Include any names mentioned along with their details (address, reviews, specialty, etc.). "
                        "Preserve all numerical data and important findings. "
                        "Include relevant reference links in your final output."
                        "\n\nRESEARCH REPORT TO SUMMARIZE:\n" + content
                    )
                    
                    response = client.chat.completions.create(
                        model=model,
                        messages=[
                            {"role": "system", "content": system_message},
                            {"role": "user", "content": user_message}
                        ],
                        temperature=0,
                        max_tokens=2000,
                    )


                    return response.choices[0].message.content

                # Run the summarization
                summary = asyncio.run(summarize_report(st.session_state.research_result))
                st.session_state.summary_result = summary
            except Exception as e:
                st.error(f"Error generating summary: {str(e)}")
                st.session_state.summary_result = "Summary generation failed. Please view the full report."

    # Always show tabs for summary and full report
    summary_tab, full_report_tab = st.tabs(["Summary", "Full Report"])

    with summary_tab:
        if st.session_state.summary_result:
            st.markdown(st.session_state.summary_result)
            st.info("This is an AI-generated summary of the full research report.")
        else:
            st.warning("Summary generation failed. Please view the full report.")

    with full_report_tab:
        st.markdown(st.session_state.research_result)

    # Download buttons for reports
    if st.session_state.task_id:
        task_id = st.session_state.task_id
        col1, col2, col3 = st.columns(3)

        with col1:
            if os.path.exists(f"outputs/{task_id}.md"):
                with open(f"outputs/{task_id}.md", "r") as f:
                    st.download_button(
                        label="Download Markdown",
                        data=f.read(),
                        file_name=f"{task_id}.md",
                        mime="text/markdown"
                    )

        with col2:
            if os.path.exists(f"outputs/{task_id}.docx"):
                with open(f"outputs/{task_id}.docx", "rb") as f:
                    st.download_button(
                        label="Download DocX",
                        data=f.read(),
                        file_name=f"{task_id}.docx",
                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                    )

        with col3:
            if os.path.exists(f"outputs/{task_id}.json"):
                with open(f"outputs/{task_id}.json", "r") as f:
                    st.download_button(
                        label="Download JSON",
                        data=f.read(),
                        file_name=f"{task_id}.json",
                        mime="application/json"
                    )

        # Add option to download the summary if available
        if st.session_state.summary_result:
            # Create a DOCX file for the summary
            try:
                from htmldocx import HtmlToDocx
                from docx import Document
                import mistune
                import io

                # Convert summary markdown to HTML
                html = mistune.html(st.session_state.summary_result)

                # Create a document object
                doc = Document()

                # Convert the html generated from the summary to document format
                HtmlToDocx().add_html_to_document(html, doc)

                # Save to a BytesIO object instead of a file
                docx_bytes = io.BytesIO()
                doc.save(docx_bytes)
                docx_bytes.seek(0)

                # Offer the DOCX for download
                st.download_button(
                    label="Download Summary (DOCX)",
                    data=docx_bytes,
                    file_name=f"{task_id}_summary.docx",
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                )
            except Exception as e:
                st.error(f"Error creating DOCX file: {str(e)}")
                # Fallback to markdown if DOCX creation fails
                st.download_button(
                    label="Download Summary (Markdown)",
                    data=st.session_state.summary_result,
                    file_name=f"{task_id}_summary.md", 
                    mime="text/markdown"
                )