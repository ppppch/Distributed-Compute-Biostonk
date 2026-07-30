"""
Server computer

Loads the trained model once at startup, then accepts chunks of
image data over the network and returns predictions.
"""

from fastapi import FastAPI
from pydantic import BaseModel
import numpy as np
import joblib

app = FastAPI()

#loads the model once, when the server starts
model = joblib.load("baseline_model.joblib")

#defines the shape of data we expect to receive
class PredictRequest(BaseModel):
    images: list[list[float]]      #a list of images, each image is a list of 64 numbers
    original_index: list[int]      #each image's original position, for reassembly later

@app.get("/")
def read_root():
    return {"status": "Server is running"}

@app.post("/predict")
def predict(request: PredictRequest):
    X = np.array(request.images)              #convert the incoming list back into a numpy array
    predictions = model.predict(X)             #run inference

    return {
        "predictions": predictions.tolist(),   #numpy arrays aren't JSON-friendly, convert to a plain list
        "original_index": request.original_index
    }