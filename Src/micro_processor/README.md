# Run the mp phase

## Create venv and install dependence

I am using `uv` for venv manager. [UV Document](https://docs.astral.sh/uv/)

```
uv venv
```
Activate venv
```
source .venv/bin/activate
```
Install dependence
```
uv pip install -r requirements.txt
```

## Run plate manager web ui 
> You must run this WEB UI first

```
python plate_manager_webui.py
```

Access web at: `http://[raspberry_pi_IP]:5000` e.g: [http://127.0.0.1:5000](http://127.0.0.1:5000)

## Run the main backend

```
python main.py
```

