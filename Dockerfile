FROM umihico/aws-lambda-selenium-python:latest

ENV AM_I_IN_A_DOCKER_CONTAINER true
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY main.py ./
CMD [ "main.handler" ]
