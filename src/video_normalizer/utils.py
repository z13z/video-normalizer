def format_duration(seconds):
    minutes = int(seconds / 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}h {minutes}m"
    else:
        return f"{minutes}m"