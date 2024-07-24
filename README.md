### Salvation

```
go mod tidy
go run main.go
```

Once installed, the best way to visualize would be,

```
match(n:ENTITY)
where n.view = 2
return n
```

### Visualization

Two ways - Download bloom desktop for optimal performance/development (insertion of queries is multiple times faster). The other option is cloud instance (use the credentials from main.go)

### Ideas

The idea is to have multiple views that will crunch the data in a consumable format for the end user inorder to make informed decisions in less amount of time

## Running Dev/Test Instances

Neo4j:   http://18.215.233.59:7474/browser/<br />
Skynet:   http://18.215.233.59:3000/view1<br />
SSH access: use the project key

```
To check for entity dupes, use:
MATCH (n:ENTITY)
RETURN (n)
```
