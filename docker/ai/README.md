# AI Tools

## Ollama + Open WebUI

Inspired to setup the stack by this Reddit thread: [The year is 2024, self hosted LLM is insane](https://www.reddit.com/r/selfhosted/comments/1b2of7h/the_year_is_2024_self_hosted_llm_is_insane/)

Run model with Ollama via CLI: `docker run -d -v ollama:/root/.ollama -p 11434:11434 --name ollama ollama/ollama`

Download models from model libraries:
- Ollama's own [Model Library](https://ollama.com/library/)
- [Hugging Face](https://huggingface.co/) -> [Use Ollama with any GGUF Model on Hugging Face Hub](https://huggingface.co/docs/hub/en/ollama)

### Multiple interface options

- Interact from CLI: `docker exec -it ollama ollama run mistral:7b-instruct`
- ChatGPT-like interface: Open WebUI. Configuration:
  - The first user logs in will be the admin user, this user will config signup of the rest of users
  - Use the cog icon to pull a model
  - Modelfiles ("personalities"): https://openwebui.com/modelfiles

### Access Ollama running on a firewalled machine

Special use case: Ollama is running on a machine which is not accepting incoming connections, but from that machine you can connect the host, where the application is running which want to use Ollama.
1. Configure SSH `GatewayPorts` option on the API consumer machine.
2. Start reverse SSH tunnel from ollama's host: `ssh -N -o 'ExitOnForwardFailure yes' -R *:11444:localhost:11434 <user>@<consumer-host>`
3. Use endpoint `localhost:11444` on the API consumer machine.

Man sshd -> `GatewayPorts`:
> Specifies whether remote hosts are allowed to connect to ports forwarded for the client.  By default, sshd(8) binds remote port forwardings to the loopback address.  This prevents other remote hosts from connecting to forwarded ports.
> GatewayPorts can be used to specify that sshd should allow remote port forwardings to bind to non-loopback addresses, thus allowing other hosts to connect.
> The argument may be no to force remote port forwardings to be available to the local host only, yes to force remote port forwardings to bind to the wildcard address, or clientspecified to allow the client to select the address to which the forwarding is bound.
> The default is no.

Task to start port forwarding (execute on the machine hosting Ollama):
```sh
task app:ollama-port-forward
```

### Access Ollama with OpenAI compatible API

Ollama's OpenAI-Compatible API
https://www.reddit.com/r/LocalLLaMA/comments/1apvtwo/ollamas_openaicompatible_api_and_using_it_with/

> As of v0.1.24, Ollama's API endpoint is compatible with OpenAI's API, i.e. any code that worked with the OpenAI API chat/completions will now work with your locally running ollama LLM by simply setting the api_base to http://localhost:11434/v1

#### Alternative solution

[Deploying LiteLLM Proxy](https://litellm.vercel.app/docs/proxy/deploy)

Useful for providing a single endpoint to multiple services.

Example:
`litellm --model mistral:7b-instruct --api_base https://ollama.example.com --temperature 0.6 --max_tokens 2048`

Example - with Docker:
`docker run -it --rm --name litellm-proxy -p 8888:8000 ghcr.io/berriai/litellm:main-latest --model mistral:7b-instruct --api_base https://ollama.example.com --temperature 0.6 --max_tokens 2048`

### Ollama API

https://github.com/ollama/ollama/blob/main/docs/api.md

Examples:

```sh
curl http://localhost:11434/api/generate -d '{
  "model": "mistral:7b-instruct",
  "prompt": "Why is the sky blue?"
}'
```
