import pandas as pd
import numpy as np

# Configuration
num_rows = 1000      # You can change this to 10,000 or more if you need a larger file
num_columns = 1000

print(f"Generating dataset with {num_rows} rows and {num_columns} columns...")

# Initialize an empty dictionary to hold the columns
data = {}

# Column 1: Unique ID
data['ID'] = range(1, num_rows + 1)

# Columns 2 to 21: Categorical Data (Great for testing 'groupby' and aggregations)
for i in range(2, 22):
    data[f'Category_{i}'] = np.random.choice(['Alpha', 'Beta', 'Gamma', 'Delta'], num_rows)

# Columns 22 to 41: Boolean Flags (Great for testing filters)
for i in range(22, 42):
    data[f'Flag_{i}'] = np.random.choice([True, False], num_rows)

# Columns 42 to 1000: Continuous Numeric Data (Great for testing math/stats functions)
# This generates random numbers centered around 0
for i in range(42, num_columns + 1):
    data[f'Numeric_Feature_{i}'] = np.random.randn(num_rows) * 100

# Compile into a pandas DataFrame
df = pd.DataFrame(data)

# Export to CSV
filename = "large_test_dataset_1000_cols.csv"
df.to_csv(filename, index=False)

print(f"Success! Saved as {filename}")
