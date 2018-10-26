FROM python:2.7

COPY requirements.txt /tmp/

RUN apt-get update && apt-get upgrade -y && \
    apt-get install -y libdbus-1-dev vim && \
    pip install pyserial==2.4 dbus-python==1.2.8 pyopenssl==18.0.0 simplejson==3.16.0 && \
    pip install -r /tmp/requirements.txt

COPY src.tgz openmotics.conf https.crt https.key /tmp/

RUN mkdir -p /opt/openmotics && \
    cd /tmp/ && tar xzf src.tgz && mv src /opt/openmotics/python && \
    mkdir /opt/openmotics/etc && mkdir /opt/openmotics/static && \
    mv /tmp/openmotics.conf /tmp/https.crt /tmp/https.key /opt/openmotics/etc/

CMD [ "python", "/opt/openmotics/python/openmotics_service.py" ]
