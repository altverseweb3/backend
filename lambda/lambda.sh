#!/bin/bash

# Stop the script if any command fails
set -e

echo "--- [1/7] Setting up Python ${PYTHON_VERSION} environment ---"
PYTHON_VERSION="3.10.12"

# Install pyenv (if not already installed)
# This setup assumes a Unix-like environment (Linux/macOS)
if ! command -v pyenv &> /dev/null; then
    echo "Installing pyenv..."
    curl https://pyenv.run | bash
    # Add pyenv to path for this script's session
    export PATH="$HOME/.pyenv/bin:$PATH"
    eval "$(pyenv init --path)"
    eval "$(pyenv init -)"
fi

# Install and set local Python version
if ! pyenv versions --bare | grep -q "^${PYTHON_VERSION}$"; then
    echo "Installing Python ${PYTHON_VERSION}..."
    pyenv install $PYTHON_VERSION
fi
echo "Setting local Python version to ${PYTHON_VERSION}..."
pyenv local $PYTHON_VERSION

# Verify
python --version

echo "--- [2/7] Cleaning up old build artifacts ---"
rm -rf package lambda_function.zip

echo "--- [3/7] Creating temporary package/ directory ---"
mkdir package

echo "--- [4/7] Installing dependencies into package/ ---"
# Use python -m pip to ensure we're using the pyenv-managed version
python -m pip install -r requirements.txt -t package/

echo "--- [5/7] Copying application code (src/) into package/ ---"
# This copies your entire src folder into the package folder
cp -r src/ package/

echo "--- [6/7] Creating lambda_function.zip ---"
# Go *into* the package directory
cd package

# Zip the *contents* of the directory.
# This puts 'src/' and all the library folders at the ROOT of the zip file.
# The zip file will be created one level up (in the lambda/ root)
zip -r ../lambda_function.zip .

# Go back to the root directory
cd ..

echo "--- [7/7] Cleaning up temporary package directory ---"
rm -rf package/

echo "--- Build complete! ---"
echo "Your deployment package is ready: lambda_function.zip"