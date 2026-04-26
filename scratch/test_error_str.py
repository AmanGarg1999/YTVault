import concurrent.futures
try:
    raise concurrent.futures.TimeoutError()
except Exception as e:
    print(f"Error string: '{str(e)}'")
