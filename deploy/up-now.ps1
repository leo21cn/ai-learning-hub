Set-Location 'd:\szp\work\learning-hub\deploy'
docker -H 'npipe:////./pipe/docker_engine' compose -p deploy -f docker-compose.yml up -d backend frontend
$LASTEXITCODE | Write-Output
