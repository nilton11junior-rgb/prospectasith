# Auditoria digital

Abra **Auditoria digital** em Leads, nos resultados de uma busca ou na ficha da empresa. **Auditar empresas da busca** coloca os leads ainda sem relatório em uma fila local. Os resultados ficam salvos na ficha. Execute novamente para atualizar uma empresa.

A fila automática encontra os leads de prospecção que ainda precisam da primeira auditoria. Abra **Campanhas → Priorizar leads** para comparar oportunidades por evidência e próximo passo, ou abra o mini relatório na ficha. Cada campanha permite consultar seu próprio público. A primeira mensagem sugerida segue o método comercial do CRM e fica disponível para copiar e revisar. Leads em conversa ou reunião recebem o próximo passo correspondente.

O CRM visita o endereço público cadastrado e até três páginas de contato ou institucionais do mesmo domínio. A medição inicial registra o HTTP, o tempo até os cabeçalhos e o tempo de leitura do HTML. O relatório também mostra HTTPS, título, descrição, H1, viewport, meta noindex e imagens sem atributo alt. Configure a chave oficial do PageSpeed Insights na variável de ambiente `SITH_PAGESPEED_KEY` antes de iniciar o painel para obter Lighthouse móvel automaticamente. O botão **Abrir PageSpeed Insights** permite executar a medição na ferramenta do Google.

O CNPJ publicado é validado pelos dígitos verificadores e consultado na BrasilAPI. O painel pede revisão quando há vários números ou quando o cadastro diverge do nome ou localidade do lead. Para sites sem CNPJ visível, informe o número na ficha. Os contatos do cadastro são da empresa. Contatos diretos são associados aos sócios pelo nome explícito no site e o e-mail profissional precisa usar o domínio da página consultada.

O teste de WhatsApp checa a resposta do link publicado. Quando acessível, a leitura do Instagram captura os metadados públicos do perfil. A leitura estática procura Meta Pixel, Google Ads, Google Analytics e Google Tag Manager. Tags dinâmicas podem exigir execução de JavaScript ou consentimento.

O relatório separa as tags da confirmação de anúncios. Consulte as bibliotecas oficiais e salve a verificação com a evidência e a data. A pesquisa comercial brasileira usa as interfaces públicas da Meta e do Google.

Referências

- [Consulta CNPJ na BrasilAPI](https://brasilapi.com.br/docs#tag/CNPJ)
- [API PageSpeed Insights](https://developers.google.com/speed/docs/insights/v5/get-started)
- [Faixas de referência para resposta inicial](https://web.dev/articles/ttfb)
- [Biblioteca da Meta](https://www.facebook.com/ads/library/)
- [Central de transparência do Google](https://adstransparency.google.com/)
