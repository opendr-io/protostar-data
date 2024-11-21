![Alt text](img/synch.jpg)

### Data Layer For the Skynet Project

For pre-processing alerts and detection artifacts, and their entities, for ingestion into the Skynet knowledge graph. Prerequisites: an instance of neo4j (https://neo4j.com/product/neo4j-graph-database/) You can use the Python module in the recognizer folder to process your raw alerts or you can ingest the sample alerts in the data folder which are pre-processed. 

This doc covers setup of the entire project: (https://github.com/cyberdyne-ventures/skynet-data/blob/main/SETUP.md)

Once installed, this is a sort of select all in the neo4j data layer:

```
match(n:ENTITY)
where n.view = 2
return n
```
### Visualization

After the data layer is running, download and run the web server which provides a user interface: https://github.com/cyberdyne-ventures/skynet-web

### Ideas



