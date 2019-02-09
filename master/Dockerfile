FROM python
RUN pip3 install flask pymongo requests
COPY master.py /
EXPOSE 5000
ENTRYPOINT ["python3", "master.py"]
