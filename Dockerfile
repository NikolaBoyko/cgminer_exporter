FROM python:3.8-alpine
RUN pip install tornado
COPY . .
CMD [ "python", "./cgminer_exporter.py" ]
