# scenarios/

`test_50.pkl` — 50 escenarios de test, con semilla separada de train/val (`ai/CLAUDE.md` §2.7).

**Se congela la primera vez que se genera y nunca se vuelve a tocar.** No se regenera, y no
se usa para elegir hiperparámetros bajo ninguna circunstancia.

El archivo `.pkl` está en `.gitignore` (`ai/scenarios/*.pkl`) por ser un artefacto binario
grande, no código. Este `README.md` sí se versiona para que la carpeta y la regla queden
documentadas en el repo aunque el `.pkl` todavía no exista.
