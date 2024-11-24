import streamlit as st
import sys
import base64
import pandas as pd
from e2b_code_interpreter import Sandbox
from anthropic import Anthropic
import numpy as np
import os

# Assuming you have a function to get secrets
def get_secret(key):
    # Replace this with your actual secret retrieval logic
    return os.getenv(key)  # Example using environment variables

# Load your secret keys
anthropic_api_key = get_secret("ANTHROPIC_API_KEY")  # Replace with your actual secret key name
e2b_api_key = get_secret("E2B_API_KEY")  # Replace with your actual secret key name

async def main():
    st.title("CSV Data Analyzer")
    st.write("Upload your CSV file and select columns to analyze")
    
    # Create sandbox with error handling
    try:
        sbx = Sandbox()
    except Exception as e:
        st.error(f"Failed to create sandbox: {str(e)}")
        return  # Exit the main function if sandbox creation fails
    
    # Streamlit file uploader
    uploaded_file = st.file_uploader("Upload your CSV file", type="csv")
    
    if uploaded_file is not None:
        try:
            # Read the CSV file to get column names
            df = pd.read_csv(uploaded_file)
            columns = df.columns.tolist()
            
            # Reset the file pointer for later use
            uploaded_file.seek(0)
            
            # Upload the dataset to the sandbox
            dataset_path = sbx.files.write("dataset.csv", uploaded_file)
            
            # Create column selection interface
            st.subheader("Select Columns for Analysis")
            
            # Detect numeric columns
            numeric_columns = df.select_dtypes(include=['int64', 'float64']).columns.tolist()
            date_columns = [col for col in columns if 'date' in col.lower() or 
                          df[col].dtype == 'datetime64[ns]' or 
                          (df[col].dtype == 'object' and pd.to_datetime(df[col], errors='coerce').notna().any())]
            
            # Column selection
            x_axis = st.selectbox("Select X-axis column (usually date/time)", date_columns if date_columns else columns)
            y_axis = st.selectbox("Select Y-axis column (numeric data)", numeric_columns if numeric_columns else columns)
            
            # Chart type selection
            chart_type = st.selectbox("Select chart type", 
                                    ["Line Chart", "Scatter Plot", "Bar Chart"])
            
            if st.button("Generate Analysis"):
                async def run_ai_generated_code(ai_generated_code: str):
                    st.write('Running the analysis in the sandbox....')
                    
                    try:
                        execution = sbx.run_code(ai_generated_code)
                        st.write('Analysis complete!')

                        if execution.error:
                            st.error('Error in analysis:')
                            st.error(execution.error.name)
                            st.error(execution.error.value)
                            st.error(execution.error.traceback)
                            return

                        for idx, result in enumerate(execution.results):
                            if result.png:
                                png_data = base64.b64decode(result.png)
                                st.image(png_data, caption=f'Chart {idx + 1}', use_column_width=True)

                    except Exception as e:
                        st.error(f'An error occurred: {str(e)}')
                        return

                prompt = f"""
                I have a CSV file that's saved in the sandbox at {dataset_path.path}.
                The user wants to analyze the relationship between '{x_axis}' (x-axis) and '{y_axis}' (y-axis) using a {chart_type}.
                
                Write Python code that:
                1. Reads the CSV file
                2. Processes the data appropriately (handle missing values, convert dates if needed)
                3. Creates a {chart_type.lower()} using matplotlib or seaborn
                4. Adds proper labels, title, and formatting
                5. If the x-axis is a date, ensure it's properly formatted
                6. Include basic statistical information in the title or caption
                
                Make sure to handle potential errors and data type conversions.
                """

                anthropic = Anthropic()
                st.write("Generating analysis...")
                msg = anthropic.messages.create(
                    model='claude-3-haiku-20240307',
                    max_tokens=1024,
                    messages=[
                        {"role": "user", "content": prompt}
                    ],
                    tools=[
                        {
                            "name": "run_python_code",
                            "description": "Run Python code",
                            "input_schema": {
                                "type": "object",
                                "properties": {
                                    "code": { "type": "string", "description": "The Python code to run" },
                                },
                                "required": ["code"]
                            }
                        }
                    ]
                )

                for content_block in msg.content:
                    if content_block.type == "tool_use":
                        if content_block.name == "run_python_code":
                            code = content_block.input["code"]
                            st.code(code, language='python')
                            await run_ai_generated_code(code)
                            
        except Exception as e:
            st.error(f"Error processing the CSV file: {str(e)}")
            return

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
