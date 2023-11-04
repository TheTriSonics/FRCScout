# Trisonics Streamlit Data Analytics App

This app is based on the Streamlit framework: https://streamlit.io/

The framework allows us to develop a web application with just Python code. It
makes common data presentation and inestigation tasks into a sharable web
application without much more complication than working through data in a Python
notebook. For example, to pull data from a website, like TheBlueAlliance or FRC
Events, and then display it you would simply use:
```
df = pandas.read_json('https://some.api/location')
st.dataframe(df)
```

Due to the framework's friendly nature with Pandas dataframes common data
manipulation techniques are quite accesible and easy to present. Common graphing
techniques are also easily implemented. Advaned graphing or datagrids can also
be implemented with, compared to most frameworks, very little effort.

Code published to this location, in the ```release``` branch is published to
https://frcscout.streamlit.app/ and will connect to the same datasource
that the scouting application records to.