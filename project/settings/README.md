# Django Settings Configuration

This project uses a split settings configuration to support different environments:

## Settings Files

- `base.py`: Common settings shared across all environments
- `dev.py`: Development environment settings (uses SQLite)
- `test.py`: Test environment settings (uses SQL Server)
- `production.py`: Production environment settings (uses SQL Server with additional security)

## How to Use Different Settings

### Default Behavior

By default, the project uses the development settings (`dev.py`).

### Changing the Settings

To use a different settings file, set the `DJANGO_SETTINGS_MODULE` environment variable:

#### For Development (default)
``` 
set DJANGO_SETTINGS_MODULE=project.settings.development
```

#### For Test Environment
```
set DJANGO_SETTINGS_MODULE=project.settings.test
```

#### For Production
```
set DJANGO_SETTINGS_MODULE=project.settings.production
```

### In IIS/Web.config

For the IIS deployment, you can set the environment variable in your `web.config` file:

```xml
<configuration>
  <system.webServer>
    <handlers>
      <!-- Your handlers configuration -->
    </handlers>
    <environmentVariables>
      <add name="DJANGO_SETTINGS_MODULE" value="project.settings.test" />
    </environmentVariables>
  </system.webServer>
</configuration>
```

## Environment-Specific Features

- **Development**: Uses SQLite for the default database, DEBUG=True
- **Test**: Uses SQL Server for all databases, DEBUG=True/False depending if it's working!
- **Production**: Uses SQL Server with additional security settings, DEBUG=False (always unless serious errors that not appearing in TEST)
