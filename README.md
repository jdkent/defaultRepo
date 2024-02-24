# River Permit Cart Adder


- https://www.recreation.gov/permits/234622
- https://www.recreation.gov/permits/233393
- https://www.recreation.gov/permits/250014

## Setup

rename the .env.example file to .env and fill in the following fields:
- "REC_EMAIL"
- "REC_PASSWORD"

with your email and password

## Build

to build using docker, run the following command:

docker build -t river-permit .

## Run

Execute the following in one terminal:
    
```bash
docker run -p 9000:8080 --env-file .env river-permit
```

Then open another terminal and run the following command:

```bash
curl -XPOST "http://localhost:9000/2015-03-31/functions/function/invocations" -d '{ 
  "start_date": "2024-06-25",
  "end_date": "2024-07-15",
  "config": "desolation",
  "max_time": 500
}'
```

This will add the desolation permit to your cart if it is available between the dates of 2024-06-25 and 2024-07-15. The max_time parameter is the maximum time in seconds that the function will run for. If the function runs for longer than this time, it will be terminated. This is to prevent the function from running indefinitely if the permit is never available.
