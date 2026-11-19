import base64


def encode_file_to_base64(file_path: str) -> str:
    """
    Encodes the contents of a file to a base64 string.

    Args:
        file_path (str): The path to the file to be encoded.

    Returns:
        str: The base64-encoded string of the file's contents.
    """
    with open(file_path, "rb") as file:
        file_contents = file.read()
        encoded_contents = base64.b64encode(file_contents).decode("utf-8")
    return encoded_contents
