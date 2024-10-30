import importlib.metadata

try:
    __version__ = importlib.metadata.version("gptme")
except importlib.metadata.PackageNotFoundError:
    __version__ = "0.0.0 (unknown)"

if __name__ == "__main__":
    print(__version__)
