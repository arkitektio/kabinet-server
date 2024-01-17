# Kluster-Server

## Develompent

Kluster is a GraphQL API that allows you to to interact and create a variety of Clusters, and interact with
them in a variety of ways. Currently we support the following:

-   Dask Gateway Clusters
  
    These are clusters that are managed by a Dask Gateway server. They can be created and destroyed at will,
    and are designed to be ephemeral. They are designed to be used for batch processing, and are not designed
    to be used for long running jobs. Please use the "jhnnsrs/kluster-gateway" docker image to run a Dask Gateway
    server, that allows pass through authentication.


### Design

We use the Strawberry Extensions system to pass a `single` user authenticated Dask Gateway session through
the GraphQL resolvers. This should reduce the number of times we need to connect to the dask gateway server
and create new sessions.

