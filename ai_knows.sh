
# Define the files and patterns you want to include
targets=(
    "backend/app/agents/data_analyst_v3.py"
    # "backend/app/agents/utility/"*.py
    "backend/app/api/"*.py
    "backend/app/agents/utility"*.py
    # "backend/app/"*.py
    "backend/test/"*.py
    "backend/requirements.txt"
)

# Empty the file first (or create it)
> bundled_agents.txt

for f in "${targets[@]}"; do
    # Check if the file exists to avoid "No such file" errors
    if [[ -f "$f" ]]; then
        echo "--- File: $f ---" >> bundled_agents.txt
        cat "$f" >> bundled_agents.txt
        echo -e "\n\n" >> bundled_agents.txt
    fi
done

echo "Done! All content saved to bundled_agents.txt"