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
    return client["f5devices"]  # Updated database name

def save_to_mongo(db, url, username, password, hostname, status, color):
    collection = db["credentials"]
    data = {
        "url": url,
        "username": username,
        "password": password,
        "hostname": hostname,
        "status": status,
        "color": color
    }
    collection.insert_one(data)
    st.success(f"Device {hostname} added to MongoDB successfully!")

def delete_from_mongo(db, object_id):
    collection = db["credentials"]
    
    result = collection.delete_one({"_id": ObjectId(object_id)})
    
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

def get_f5_failover_status(url, username, password):
    api_url = f"{url}/mgmt/tm/cm/failover-status"
    response = requests.get(api_url, auth=(username, password), verify=False)
    
    if response.status_code == 200:
        try:
            status_entry = response.json()['entries'].popitem()[1]['nestedStats']['entries']
            status = status_entry['status']['description']
            color = status_entry['color']['description']
            return status, color
        except KeyError:
            st.error("Failed to parse failover status or color. Please check the API response.")
            return None, None
    else:
        st.error(f"Failed to retrieve failover status from {url}. Status Code: {response.status_code}")
        return None, None

def fetch_credentials(db):
    collection = db["credentials"]
    credentials = list(collection.find({}, {"_id": 1, "url": 1, "username": 1, "hostname": 1, "status": 1, "color": 1, "password": 1}))
    
    for cred in credentials:
        cred["_id"] = str(cred["_id"])
        
    return credentials

def get_color_circle_html(color):
    return f'<span style="background-color:{color};border-radius:50%;display:inline-block;width:15px;height:15px;"></span>'

def display_device_table(df):
    # Add filtering by hostname
    filter_text = st.text_input("Filter by Hostname")
    if filter_text:
        df = df[df['hostname'].str.contains(filter_text, case=False)]

    st.write("### F5 BIGIP Device List")

    # Create a container for the table
    with st.container():
        # Create columns for the table
        cols = st.columns([2, 2, 2, 2, 2, 2])

        # Add table headers
        cols[0].write("Activity")  # Updated header from Color to Activity
        cols[1].write("Hostname")
        cols[2].write("URL")
        cols[3].write("Username")
        cols[4].write("Status")
        cols[5].write("Actions")

        # Display table rows
        for index, row in df.iterrows():
            with st.container():
                cols = st.columns([2, 2, 2, 2, 2, 2])
                cols[0].markdown(get_color_circle_html(row['color']), unsafe_allow_html=True)
                cols[1].write(row['hostname'])
                cols[2].write(row['url'])
                cols[3].write(row['username'])
                cols[4].write(row['status'])
                
                # Add dropdown for actions
                selected_action = cols[5].selectbox("Action", ["Select an action", "Delete", "Show VIPs"], key=f"action_{index}")

                if selected_action == "Delete":
                    if cols[5].button("Confirm Delete", key=f"delete_{index}"):
                        db = connect_to_mongo()
                        delete_from_mongo(db, row['_id'])
                        st.session_state["credentials"] = fetch_credentials(db)  # Refresh credentials
                
                if selected_action == "Show VIPs":
                    vips = get_f5_vips(row['url'], row['username'], row['password'])
                    display_vips(vips)

    # Provide download button for the table data
    csv = df.to_csv(index=False)
    st.download_button(
        label="Download data as CSV",
        data=csv,
        file_name='devices.csv',
        mime='text/csv'
    )

def get_f5_vips(url, username, password):
    api_url = f"{url}/mgmt/tm/ltm/virtual"
    response = requests.get(api_url, auth=(username, password), verify=False)

    if response.status_code == 200:
        try:
            return response.json().get("items", [])
        except KeyError:
            st.error("Failed to parse VIPs. Please check the API response.")
            return []
    else:
        st.error(f"Failed to retrieve VIPs from {url}. Status Code: {response.status_code}")
        return []

def display_vips(vips):
    if vips:
        df_vips = pd.DataFrame(vips)
        columns_to_display = ['name', 'destination', 'pool', 'ipProtocol', 'enabled']
        df_vips = df_vips[columns_to_display]
        df_vips.columns = ['Name', 'Destination', 'Pool', 'IP Protocol', 'Status']
        st.write("### VIPs")
        st.dataframe(df_vips)
    else:
        st.write("No VIPs found.")

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
        status, color = get_f5_failover_status(url, username, password)
        
        if hostname and status and color:
            db = connect_to_mongo()
            save_to_mongo(db, url, username, password, hostname, status, color)

    # Button to fetch and display device list
    if st.button("Get Device List"):
        db = connect_to_mongo()
        st.session_state["credentials"] = fetch_credentials(db)
    
    # Display the device table if credentials exist
    if "credentials" in st.session_state and len(st.session_state["credentials"]) > 0:
        df = pd.DataFrame(st.session_state["credentials"])
        display_device_table(df)

def get_devices():
    st.title("Get Devices")

    # Fetch credentials from MongoDB
    db = connect_to_mongo()
    st.session_state["credentials"] = fetch_credentials(db)

    # Display the device table if credentials exist
    if "credentials" in st.session_state and len(st.session_state["credentials"]) > 0:
        df = pd.DataFrame(st.session_state["credentials"])
        display_device_table(df)

page = st.sidebar.selectbox("Select a page:", ["Overview", "Get Devices"])

if page == "Overview":
    overview()
elif page == "Get Devices":
    get_devices()
else:
    st.error("Invalid page selection.")
