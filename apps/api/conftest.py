import os

# Tests assert exact canned prices and must not reach the network or write anywhere.
os.environ["REALDEAL_LIVE_FLYERS"] = "0"
os.environ["REALDEAL_DATABRICKS_SYNC"] = "0"
os.environ["REALDEAL_AI_REFINE"] = "0"
