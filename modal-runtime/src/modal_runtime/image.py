import modal


image = (
    modal
    .Image
    .debian_slim(python_version="3.13")
    .uv_sync(groups=["remote"])
)
