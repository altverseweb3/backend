#!/bin/bash

# Install pyenv
curl https://pyenv.run | bash

# Install Python 3.10
pyenv install 3.10.12

# Set local Python version
pyenv local 3.10.12

# Verify Python version
python --version

# Install requirements into the current directory
pip install -r requirements.txt -t .

# Copy lambda_function.py into the current directory
cp lambda_function.py .

# Zip current directory
zip -r lambda_function.zip .

echo "zip created"

# Clean up 
# TODO: improve syntax
rm -rf $(find . -maxdepth 1 -not -name 'lambda_function.py' -not -name 'lambda_function.zip' -not -name 'README.md' -not -name 'requirements.txt' -not -name 'lambda.sh' -not -name 'tests.md' -print)

echo "Cleanup complete."