FROM ubuntu:latest

ENV PACKAGES="git \
              python3 \
              python3-dev \
              python3-pip \
              libpq-dev"

RUN apt-get update\
    && apt-get install -y $PACKAGES \
    && rm -rf /var/lib/apt/lists/*

RUN pip3 install --upgrade pip

RUN mkdir /code && cd /code

RUN git clone https://github.com/zjurelinac/east \
    && cd east \
    && python3 setup.py install

COPY requirements.txt /code

RUN pip install -r /code/requirements.txt

WORKDIR /code
CMD ["/bin/bash"]