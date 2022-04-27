FROM python:3.9-slim

#File to copy on container
#NB: You have to insert those also on bitbucket-pipelines condition in order to create new image on file edit
COPY requirements.txt  ./

#Insert here app installation
RUN pip install -r requirements.txt

#Insert here app code
COPY src/* ./

CMD ["handler.py"]