This folder contains my contribution to a MSc team project to build a chatbot robo-advisor (as part of my MSc in Data Science) for inexperienced financial investors. 

As well as being responsible for team co-ordination, project management and various design stages, I also developed this backend code to use with a locally hosted UI. 

The code is based on an optimisation and modelling code developed by a team mate and consists of 4 python files and one html styling file:





Kay's final version consists of 4 python files and one html (index) file:
- [app.py](https://github.com/KaiXin77477/Portfolio/blob/main/Robo-advisor%20Project/Code/app.py)            This is the main code or file which drives the other .py codes
- [calculate.py](https://github.com/KaiXin77477/Portfolio/blob/main/Robo-advisor%20Project/Code/calculate.py)      This is where the main calculations and optimisation occurs.
- [mapping.py](https://github.com/KaiXin77477/Portfolio/blob/main/Robo-advisor%20Project/Code/mapping.py)        This maps tickers to company names, and groups tickers into sectors
- [plots.py](https://github.com/KaiXin77477/Portfolio/blob/main/Robo-advisor%20Project/Code/plots.py)          This produces 5 graphs: 
    - Growth chart showing expected returns and uncertainty band (90th quartile) for a given user input
    - Allocation bar chart showing the proportion of different tickers that make up the portfolio
    - Pie or donut chart illustrating the proportion of different sectors in the portfolio mix
    - Correlation heat map showing the correlation between each of the tickers in the portfolio
    - Distribution of Monte Carlo generated, final portfolio values.
- [index.html](https://github.com/KaiXin77477/Portfolio/blob/main/Robo-advisor%20Project/Code/templates/index.html)        This is a style file for the webpage layout. Important: this index.html file should be stored in a subdirectory called templates. 


**In order to run this code:**
1. Download all the .py files in [this directory](https://github.com/KaiXin77477/Portfolio/tree/main/Robo-advisor%20Project/Code)
2. Ensure that the following python libraries are installed:
    - numpy, plotly, pandas, yfinance, sklearn, intertools, math, warning, flask (see [requirements.txt](https://github.com/KaiXin77477/Portfolio/blob/main/Robo-advisor%20Project/requirements.txt) for the relevant versions of python libraries)
3. Create a subdirectory called templates and download [index.html](https://github.com/KaiXin77477/Portfolio/tree/main/Robo-advisor%20Project/Code/templates) and put in that subdirectory.
4. The code will run locally, connect to port: http://127.0.0.1:5000/ and refresh for each iteration as required.
5. From Git Bash or command line type: python app.py  (assuming python has been preloaded)

Some screen shots of the UI can be found in the folder called [Screenshots of working UI](https://github.com/KaiXin77477/Portfolio/tree/main/Robo-advisor%20Project/Screenshots)


This backend version uses flask (instead of ipywidgets) to connect to local server where the user can input values directly. Chatgpt was used to write the index.html and to separate the original code into the different .py files, converting ipywidgets into flask.

**Latest version has:**
- additional tickers (stored in mapping.py and DEFAULT_ASSETS) to diversify the range of the portfolio
- tooltips (mouse hover over), user explanations and additional comments in the code
- additional results such as Sharpe & Sortino ratios, extra graphs
- additonal formatting and styling
