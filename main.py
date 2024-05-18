"""Code to create a GUI to monitor the garbage level using ESP8266 and ThingSpeak"""

import os
import time
import datetime
import socket
import json
import tkinter as tk
import asyncio
from threading import Thread
import paho.mqtt.publish as publish
from dotenv import load_dotenv
import customtkinter
from azure.iot.device.aio import IoTHubDeviceClient


customtkinter.set_appearance_mode("dark")
customtkinter.set_default_color_theme("green")
load_dotenv()

# Define global variables
server_address = (os.getenv("SERVER_ADDRESS"), int(os.getenv("SERVER_PORT")))
CHANNEL_ID = os.getenv("CHANNEL_ID")
MQTT_HOST = os.getenv("MQTT_HOST")
T_TRANSPORT = os.getenv("T_TRANSPORT")
T_PORT = int(os.getenv("T_PORT"))
MQTT_CLIENT_ID = os.getenv("MQTT_CLIENT_ID")
MQTT_USERNAME = os.getenv("MQTT_USERNAME")
MQTT_PASSWORD = os.getenv("MQTT_PASSWORD")
RECONNECT_DELAY = int(os.getenv("RECONNECT_DELAY"))
IS_SERVER_RUNNING = False
SERVER_SOCKET = None
CONNECTION_STRING = os.getenv("CONNECTION_STRING")


async def send_to_azure_iot_hub(data):
    """Send the given data to Azure IoT Hub"""
    try:
        device_client = IoTHubDeviceClient.create_from_connection_string(CONNECTION_STRING)
        await device_client.connect()
        print("Sending data to Azure IoT Hub:", data)
        await device_client.send_message(data)
        await device_client.disconnect()
    except Exception as e:
        print("Exception:", e)

# Function to publish data to ThingSpeak
def send_to_thingspeak(data):
    """Publish the given data to ThingSpeak channel using MQTT protocol"""
    try:
        topic = "channels/" + CHANNEL_ID + "/publish"
        payload = "field1=" + str(data)
        publish.single(
            topic,
            payload,
            hostname=MQTT_HOST,
            transport=T_TRANSPORT,
            port=T_PORT,
            client_id=MQTT_CLIENT_ID,
            auth={"username": MQTT_USERNAME, "password": MQTT_PASSWORD},
        )
    except Exception as e:
        print("Exception:", e)


# Function to receive data from ESP8266
def receive_data_from_esp():
    """Receive data from ESP8266 and update the GUI with the garbage level"""
    global SERVER_SOCKET
    while True:
        try:
            SERVER_SOCKET = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            SERVER_SOCKET.bind(server_address)
            SERVER_SOCKET.listen(1)
            print("Waiting for ESP8266")
            conn, addr = SERVER_SOCKET.accept()
            with conn:
                print("Connected to", addr)
                while True:
                    if SERVER_SOCKET is None:
                        break
                    data = conn.recv(1024)
                    if not data:
                        print("Connection closed")
                        break
                    data_str = data.decode().strip()
                    if data_str.isdigit():
                        garbage_level = float(data_str)
                        if 0 <= garbage_level <= 1000:
                            print("Garbage Level:", garbage_level)
                            update_gui(garbage_level)
                            if thingspeak_switch.get():
                                send_to_thingspeak(garbage_level)
                            if azure_IOT_hub_switch.get():
                                data ={
                                    "device_id": "edge_server_1",
                                    "garbage_level": garbage_level,
                                    "edge_timestamp": str(datetime.datetime.now())
                                }
                                asyncio.run(send_to_azure_iot_hub(json.dumps(data)))

        except socket.timeout:
            print("Socket timeout occurred. Retrying in", RECONNECT_DELAY, "seconds...")
            time.sleep(RECONNECT_DELAY)
        except Exception as e:
            print("Exception occurred:", e)
        finally:
            if SERVER_SOCKET:
                SERVER_SOCKET.close()
            SERVER_SOCKET = None


# Function to update GUI with garbage level
def update_gui(garbage_level):
    """Update the garbage level label with the given garbage level"""
    global IS_SERVER_RUNNING
    if not IS_SERVER_RUNNING:
        return
    garbage_label.configure(text="Garbage Level: {:.2f}".format(garbage_level))


def update_server_status(status):
    """Update the server status label with the given status"""
    server_status_label.configure(text=status)


# Function to start the server
def start_server():
    """Start the server in a separate thread"""
    global IS_SERVER_RUNNING
    if IS_SERVER_RUNNING:
        print("Waiting for ESP8266...")
        update_server_status("Server Status: Running")
        start_button.configure(state=tk.DISABLED)
        stop_button.configure(state=tk.NORMAL)
        return
    IS_SERVER_RUNNING = True
    update_server_status("Server Status: Running")
    server_thread = Thread(target=receive_data_from_esp)
    server_thread.daemon = True
    server_thread.start()
    start_button.configure(state=tk.DISABLED)
    stop_button.configure(state=tk.NORMAL)


# Function to stop the server
def stop_server():
    """Stop the server and close the GUI"""
    server_status_label.configure(text="Server Status: Stopped")
    print("Sever stopped")
    start_button.configure(state=tk.NORMAL)
    stop_button.configure(state=tk.DISABLED)


# Create GUI
root = customtkinter.CTk()
root.title("Garbage Level Monitoring")
root.geometry("800x400")
font = customtkinter.CTkFont(family="Jetbrains Mono", size=20)

# Create a frame to hold the buttons and labels
frame = customtkinter.CTkFrame(master=root)
frame.pack(fill=tk.BOTH, expand=True)  # Set the frame to fill the whole window


# Garbage level label
garbage_label = customtkinter.CTkLabel(frame, font=font, text="Garbage Level: ")
garbage_label.grid(row=0, column=0, columnspan=2, pady=20)

# Start button
start_button = customtkinter.CTkButton(
    frame, font=font, width=150, height=50, text="Start Server", command=start_server
)
start_button.grid(row=1, column=1, padx=15)

# Stop button
stop_button = customtkinter.CTkButton(
    frame,
    font=font,
    width=150,
    height=50,
    text="Stop Server",
    command=stop_server,
    state=tk.DISABLED,
)
stop_button.grid(row=1, column=2, padx=10)

azure_IOT_hub_switch = customtkinter.CTkSwitch(
    frame, font=font, text="Send data to Azure IoT Hub", command=None, state=True
)
azure_IOT_hub_switch.grid(row=3, column=0, columnspan=2, pady=20, padx=20, sticky="w")

thingspeak_switch = customtkinter.CTkSwitch(
    frame, font=font, text="Send data to ThingSpeak", command=None, state=True
)
thingspeak_switch.grid(row=4, column=0, columnspan=2, pady=20, padx=20, sticky="w")

# Server status label
server_status_label = customtkinter.CTkLabel(frame, font=font, text="Server Status: ")
server_status_label.grid(row=0, column=2, columnspan=2, pady=20)

# Call the GUI
if __name__ == "__main__":
    root.mainloop()
