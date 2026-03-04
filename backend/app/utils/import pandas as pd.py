import pandas as pd

# Assuming df is already defined and contains the schema context provided
# Example DataFrame creation for demonstration purposes
data = {
    'Index': [0, 1, 2],
    'Name': ['Item1', 'Item2', 'Item3'],
    'Description': ['Desc1', 'Desc2', 'Desc3'],
    'Brand': ['BrandA', 'BrandB', 'BrandC'],
    'Category': ['Cat1', 'Cat2', 'Cat3'],
    'Price': [10.5, 20.75, 30.0],
    'Currency': ['USD', 'EUR', 'GBP'],
    'Stock': [10, 20, 30],
    'EAN': ['EAN1', 'EAN2', 'EAN3'],
    'Color': ['Red', 'Blue', 'Green'],
    'Size': ['S', 'M', 'L'],
    'Availability': ['Yes', 'No', 'Yes'],
    'Internal ID': [1, 2, 3]
}
df = pd.DataFrame(data)

# Calculate the median of the 'Price' column
result = df['Price'].median()