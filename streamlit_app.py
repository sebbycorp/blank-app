import streamlit as st
import requests
from pymongo import MongoClient
import pandas as pd
import urllib3
from bson.objectid import ObjectId

# Suppress only the single InsecureRequestWarning from urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def connect_to_mongo():
    client = MongoClient("mongodb://myadmin:mypassword@localhost:27017/")
    return client["f5bigip"]

def save_to_mongo(db, url, username, password, hostname):
    collection = db["credentials"]
    data = {
        "url": url,
        "username": username,
        "password": password,
        "hostname": hostname
    }
    collection.insert_one(data)
    st.success(f"Device {hostname} added to MongoDB successfully!")

def delete_from_mongo(db, object_id):
    collection = db["credentials"]
    
    # Debug: Print the ObjectId to be deleted
    st.write(f"Attempting to delete with ObjectId: {object_id}")
    
    result = collection.delete_one({"_id": ObjectId(object_id)})
    
    # Debug: Check how many documents were deleted
    if result.deleted_count > 0:
        st.success(f"Deleted device with ObjectId: {object_id}")
        st.session_state["credentials"] = fetch_credentials(db)  # Refresh credentials
    else:
        st.error(f"Failed to delete device with ObjectId: {object_id}. Please check if the entry exists.")

def get_f5_hostname(url, username, password):
    api_url = f"{url}/mgmt/tm/sys/global-settings"
    response = requests.get(api_url, auth=(username, password), verify=False)
    
    if response.status_code == 200:
        hostname = response.json().get("hostname")
        return hostname
    else:
        st.error(f"Failed to retrieve hostname from {url}. Status Code: {response.status_code}")
        return None

def fetch_credentials(db):
    collection = db["credentials"]
    credentials = list(collection.find({}, {"_id": 1, "url": 1, "username": 1, "hostname": 1}))
    
    # Convert ObjectId to string for compatibility with AgGrid
    for cred in credentials:
        cred["_id"] = str(cred["_id"])
        
    return credentials

def overview():
    st.title("Overview")

    # Input fields for URL, username, and password
    url = st.text_input("Enter API URL (https:// required)")
    username = st.text_input("Enter Username")
    password = st.text_input("Enter Password", type="password")

    # Button to save data to MongoDB
    if st.button("Add Device"):
        if not url.startswith("https://"):
            st.error("URL must start with https://")
            return
        hostname = get_f5_hostname(url, username, password)
        if hostname:
            db = connect_to_mongo()
            save_to_mongo(db, url, username, password, hostname)

    # Button to fetch and display device list
    if st.button("Get Device List"):
        db = connect_to_mongo()
        st.session_state["credentials"] = fetch_credentials(db)
    
    # Always display the credentials if they exist in session state
    if "credentials" in st.session_state and len(st.session_state["credentials"]) > 0:
        df = pd.DataFrame(st.session_state["credentials"])

        # Add filtering by hostname
        filter_text = st.text_input("Filter by Hostname")
        if filter_text:
            df = df[df['hostname'].str.contains(filter_text, case=False)]

        st.write("### Saved Credentials")

        # Create a container for the table
        with st.container():
            # Create columns for the table
            cols = st.columns([2, 2, 2, 2])

            # Add table headers
            cols[0].write("Hostname")
            cols[1].write("URL")
            cols[2].write("Username")
            cols[3].write("Actions")

            # Display table rows
            for index, row in df.iterrows():
                with st.container():
                    cols = st.columns([2, 2, 2, 2])
                    cols[0].write(row['hostname'])
                    cols[1].write(row['url'])
                    cols[2].write(row['username'])
                    
                    # Add dropdown for actions
                    selected_action = cols[3].selectbox("Action", ["Select an action", "Delete"], key=f"action_{index}")

                    if selected_action == "Delete":
                        if cols[3].button("Confirm Delete", key=f"delete_{index}"):
                            db = connect_to_mongo()
                            delete_from_mongo(db, row['_id'])
                            st.session_state["credentials"] = fetch_credentials(db)  # Refresh credentials

        # Provide download button for the table data
        csv = df.to_csv(index=False)
        st.download_button(
            label="Download data as CSV",
            data=csv,
            file_name='devices.csv',
            mime='text/csv'
        )

def get_devices():
    st.title("Get Devices")

    # Retrieve values from session state
    url = st.session_state.get("url", "")
    username = st.session_state.get("username", "")
    password = st.session_state.get("password", "")

    # Input fields (pre-filled with values from overview)
    url = st.text_input("Enter API URL", value=url)
    username = st.text_input("Enter Username", value=username)
    password = st.text_input("Enter Password", type="password", value=password)

page = st.sidebar.selectbox("Select a page:", ["Overview", "Get Devices"])

if page == "Overview":
    overview()
elif page == "Get Devices":
    get_devices()
else:
    st.error("Invalid page selection.")
