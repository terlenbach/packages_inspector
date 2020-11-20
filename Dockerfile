FROM python:3.8-slim

WORKDIR /usr/src/app

# We first install the requirements to speed up the build process
# if the requirements haven't changed
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN pip install --no-cache-dir --no-deps .

ENTRYPOINT ["packages_inspector"]
