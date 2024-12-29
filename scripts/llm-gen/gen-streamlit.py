# Run with: streamlit run gen-streamlit.py --server.headless true

import streamlit as st
from gen import LLMTextProcessor

# Initialize the text processor
processor = LLMTextProcessor()

# Load available templates from the "templates" folder
template_folder = "templates"
template_files = processor.get_template_names()

# CSS to use fixed-width font for text areas
st.markdown("""
<style>
    textarea {
        font-family: monospace !important;
    }
</style>
""", unsafe_allow_html=True)

# Streamlit interface
st.title("LLM Text Processor")

# Sidebar configuration
st.sidebar.header("Configuration")

# Model selection
model = st.sidebar.text_input("Model", value="")  # instruct

# Temperature configuration
temperature = st.sidebar.slider("Temperature", min_value=0.0, max_value=1.0, value=0.7, step=0.1)

# Template selection
template = st.sidebar.selectbox("Template", options=template_files)

# Main input text
# st.header("Input Text")
input_text = st.text_area("Enter the input text:", height=200)

# Process button
if st.button("Process"):
    if not input_text.strip():
        st.error("Please enter some text.")
    else:
        # Get the response using the processor
        try:
            response = processor.respond(
                input_text=input_text,
                template=template,
                model=model,
                temperature=temperature,
            )
            st.success("Processing Complete!")
            st.text_area("Output:", response, height=300)

            # Display the response as markdown
            st.markdown("### Formatted Output:")
            st.markdown(response)
        except Exception as e:
            st.error(f"An error occurred: {str(e)}")
