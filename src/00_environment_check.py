import sys
import numpy as np
import pandas as pd
import scipy
import sklearn
import statsmodels
import matplotlib
import plotly
import requests
import bs4
import lxml
import openpyxl

print("=" * 50)
print("DATADOG PROJECT — ENVIRONMENT CHECK")
print("=" * 50)

print("\nPython")
print(sys.version)
print(sys.executable)

print("\nCore packages")
print("numpy:", np.__version__)
print("pandas:", pd.__version__)
print("scipy:", scipy.__version__)
print("scikit-learn:", sklearn.__version__)
print("statsmodels:", statsmodels.__version__)

print("\nVisualization")
print("matplotlib:", matplotlib.__version__)
print("plotly:", plotly.__version__)

print("\nData acquisition")
print("requests:", requests.__version__)
print("beautifulsoup4:", bs4.__version__)
print("lxml:", lxml.__version__)
print("openpyxl:", openpyxl.__version__)

print("\n" + "=" * 50)
print("ENVIRONMENT READY")
print("=" * 50)