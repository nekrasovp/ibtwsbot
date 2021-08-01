FROM python:3.9-alpine
LABEL Author="Nekasov Pavel"

# The enviroment variable ensures that the python output is set straight
# to the terminal with out buffering it first
ENV PYTHONUNBUFFERED 1

# Setup directory structure
RUN mkdir /app
COPY . /app
WORKDIR /app

# Install dependencies
RUN pip install -r /app/requirements.txt

# Setup security issues
RUN useradd --no-log-init --shell /bin/bash user
USER user

EXPOSE 7497
