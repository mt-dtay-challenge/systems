FROM python
RUN pip3 install flask requests
COPY slave.py /
EXPOSE 5000
ENTRYPOINT ["python3", "slave.py"]
