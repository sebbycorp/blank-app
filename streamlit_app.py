import streamlit as st
import requests

# Title of the app
st.title("🔗 REST API Call App")

# Input fields
url = st.text_input("Enter API URL")
username = st.text_input("Enter Username")
password = st.text_input("Enter Password", type="password")

# Submit button
if st.button("Submit"):
    if url and username and password:
        try:
            # Making the REST API call
            response = requests.get(url, auth=(username, password))
            response.raise_for_status()  # Raise an exception for HTTP errors

            # Display the JSON output
            st.json(response.json())
        except requests.exceptions.RequestException as e:
            st.error(f"API call failed: {e}")
    else:
        st.warning("Please fill in all fields.")

# Footer or instructions
st.write("Make sure your API URL is correct, and your credentials are valid.")
