'try:
    median_price = df[\'Price\'].median()
    result = {"success": True, "result": median_price}
except Exception as e:
    result = {"success": False, "result": str(e)}
print(json.dumps(result))'
