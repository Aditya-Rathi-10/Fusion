# base image  
FROM python:3.8

# setup environment variable for work directory  
ENV FUSION_HOME=/home/app

# make work directory  
RUN mkdir -p $FUSION_HOME

# set work directory  
WORKDIR $FUSION_HOME

# set environment variables  
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# copy requirements file
COPY requirements.txt $FUSION_HOME

# install dependencies
# arabic-reshaper==2.1.1 has legacy metadata that breaks with newer pip.
RUN pip install "pip<24.1" && pip install -r requirements.txt

# copy api directory to docker's work directory. 
COPY . $FUSION_HOME

# port where the Django app runs  
EXPOSE 8000

# start server  
CMD ["/bin/bash","docker-entrypoint.sh"]
