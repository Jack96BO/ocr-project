import os

def list_files(directory):
    return [os.path.join(directory, f) for f in os.listdir(directory)]