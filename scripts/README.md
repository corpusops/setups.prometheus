# tools for working with prometheusscripts

## install as a python lib
```bash
pip install prometheusscripts
```

## Run in dev
### Configure
```bash
cp .env.dist .env
cp .env.local.dist .env.local
printf "USER_UID=$(id -u)\nUSER_GID=$(id -g)\n">>.env
```

### Build
```bash
eval $(egrep -hv '^#|^\s*$' .env .env.local|sed  -e "s/^/export /g"| sed -e "s/=/='/" -e "s/$/'/g"|xargs)
COMPOSE_FILE="docker-compose.yml:docker-compose-build.yml" docker-compose build
```

### Run

```bash
docker-compose run --rm prometheusscripts shell
```

```bash
sed "/COMPOSE_FILE/d" .env
echo COMPOSE_FILE=docker-compose.yml:docker-compose-dev.yml"
docker-compose up -d --force-recreate
docker-compose exec -u prometheusscripts prometheusscripts bash
```


## Doc
see also [USAGE](./USAGE.md) (or read below on pypi)
