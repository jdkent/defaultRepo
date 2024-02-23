FROM umihico/aws-lambda-selenium-python:latest

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY main.py ./
CMD [ "main.handler" ]
