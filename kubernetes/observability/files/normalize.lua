-- Only explicit bounded identity fields reach Loki; application JSON cannot
-- overwrite Kubernetes identity. The original message is always retained.
function normalize(tag, timestamp, input)
    local k = input["kubernetes"] or {}
    local labels = k["labels"] or {}
    local record = {}
    record["message"] = input["log"] or ""
    record["namespace"] = k["namespace_name"] or "unknown"
    record["app"] = "unknown"
    for _, key in ipairs({"app.kubernetes.io/instance", "app.kubernetes.io/name", "app"}) do
        if labels[key] and labels[key] ~= "" then
            record["app"] = labels[key]
            break
        end
    end
    record["container"] = k["container_name"] or "unknown"
    record["pod"] = k["pod_name"]
    record["node"] = k["host"]
    record["stream"] = input["stream"]
    record["source"] = "container"
    record["parsed"] = input["parsed"]
    return 1, timestamp, record
end
