import pandas as pd
import streamlit as st
import plotly.express as px
from datetime import datetime

st.set_page_config(page_title='Produção CCH', layout='wide')


class Relatorios:

    def __init__(self, nome_arquivo):
        self.nome_arquivo = nome_arquivo

    @staticmethod
    @st.cache_data
    def importar_arquivos(nome_arquivo):
        return pd.read_excel(nome_arquivo, index_col=False)

    def ajustar_data_hora(self, df):
        def ajustar_hora_operacional(h, data):
            if h >= 6:
                return h - 6, data
            else:
                return h + 18, data - pd.Timedelta(days=1)

        df['Hora separação'] = pd.to_datetime(df['Hora separação'], format='%H')
        df['hora'] = df['Hora separação'].dt.hour
        df['Data ajustada'] = df['Data separação']

        df['Hora Operacional'], df['Data ajustada'] = zip(*df.apply(
            lambda row: ajustar_hora_operacional(row['hora'], row['Data separação']), axis=1
        ))

        df['Dia'] = df['Data ajustada'].dt.strftime('%d')
        return df

    def tratar_dados(self):
        df = (
            self.importar_arquivos(self.nome_arquivo)
            .rename(columns={
                'id_local': 'Tipo separação',
                'funcionario': 'Funcionário',
                'dt_separacao': 'Data separação',
                'hr_separacao': 'Hora separação',
                'qt_apanha': 'Bipes',
                'qt_unidades': 'Unidades',
                'qt_caixas': 'Caixas',
                'cd_usuario_separacao': 'Código funcionário',
                'tempo': 'Tempo'
            })
            .drop(columns=['cd_pessoa_filial'])
            .astype({
                'Tipo separação': 'string',
                'Funcionário': 'string',
                'Data separação': 'datetime64[ns]',
            })
        )

        df['Tempo'] = pd.to_timedelta(df['Tempo'], unit='s')

        df['Tipo separação'] = df['Tipo separação'].replace({
            'Caixa Fechada': 'Box',
            'Palete': 'Box',
            'Flow Rack': 'Ilha'
        })

        colunas_soma = ['Bipes', 'Unidades', 'Caixas']
        colunas_identificacao = ['Data separação', 'Hora separação', 'Funcionário', 'Código funcionário']

        df = df.groupby(colunas_identificacao, as_index=False).agg(
            {**{col: 'sum' for col in colunas_soma}, 'Tempo': 'first', 'Tipo separação': 'first'}
        )

        df['Mes_Ano'] = df['Data separação'].dt.strftime('%m/%Y')

        return self.ajustar_data_hora(df)


class Dashboard:

    def __init__(self, dados):
        self.df_original = dados

    def criar_filtros(self):
        col1, col2, col3, col4 = st.columns(4)

        # Adiciona 'Todos' como primeira opção em cada filtro
        mes_ano_opcoes = ['Todos'] + sorted(self.df_original['Mes_Ano'].unique())
        funcionario_opcoes = ['Todos'] + sorted(self.df_original['Funcionário'].unique())
        tipo_separacao_opcoes = ['Todos'] + sorted(self.df_original['Tipo separação'].unique())
        dia_opcoes = ['Todos'] + sorted(self.df_original['Dia'].unique())
        with st.container(border=True):
            with col1:
                mes_ano = st.selectbox('🗓 Mês:', mes_ano_opcoes, key='mes_ano')

            with col2:
                dia = st.selectbox('📅 Dia:', dia_opcoes, key='dia')

            with col3:
                tipo_separacao = st.selectbox('📦 Tipo de separação:', tipo_separacao_opcoes, key='tipo_separacao')

            with col4:
                funcionario = st.selectbox('👷‍♂️ Funcionário:', funcionario_opcoes, key='funcionario')

            return mes_ano, funcionario, tipo_separacao, dia

    def aplicar_filtros(self, mes_ano, funcionario, tipo_separacao, dia):
        df_filtrado = self.df_original

        if mes_ano != 'Todos':
            df_filtrado = df_filtrado[df_filtrado['Mes_Ano'] == mes_ano]
        if funcionario != 'Todos':
            df_filtrado = df_filtrado[df_filtrado['Funcionário'] == funcionario]
        if tipo_separacao != 'Todos':
            df_filtrado = df_filtrado[df_filtrado['Tipo separação'] == tipo_separacao]
        if dia != 'Todos':
            df_filtrado = df_filtrado[df_filtrado['Dia'] == dia]

        return df_filtrado

    def mostrar_cards(self, df_filtrado):
        col1, col2, col3, col4 = st.columns(4)

        # Dados para o cálculo
        total_bipes = df_filtrado['Bipes'].sum()
        total_caixas = df_filtrado['Caixas'].sum()
        total_unidades = df_filtrado['Unidades'].sum()

        df_media_box = (df_filtrado[df_filtrado['Tipo separação'] == 'Box'].groupby(['Mes_Ano', 'Dia', 'Funcionário']).
                        agg({'Bipes': 'sum', 'Tempo': 'sum'}).reset_index())
        # df_media_box['Horas trabalhadas'] = df_media_box['Tempo'].dt.total_seconds() / 3600
        df_media_box['Bipes/hora'] = df_media_box['Bipes'] / 9
        df_media_box = df_media_box.sort_values(by='Bipes', ascending=False)
        df_media_box = df_media_box.groupby('Funcionário')['Bipes/hora'].mean().reset_index()
        df_media_box = df_media_box.sort_values(by='Bipes/hora', ascending=False).head(5)
        media_homem_hora_box = df_media_box['Bipes/hora'].head(5).mean()

        df_media_ilha = (
            df_filtrado[df_filtrado['Tipo separação'] == 'Ilha'].groupby(['Mes_Ano', 'Dia', 'Funcionário']).
            agg({'Bipes': 'sum', 'Tempo': 'sum'}).reset_index())
        # df_media_ilha['Horas trabalhadas'] = df_media_ilha['Tempo'].dt.total_seconds() / 3600
        df_media_ilha['Bipes/hora'] = df_media_ilha['Bipes'] / 9
        df_media_ilha = df_media_ilha.sort_values(by='Bipes', ascending=False)
        df_media_ilha = df_media_ilha.groupby('Funcionário')['Bipes/hora'].mean().reset_index()
        df_media_ilha = df_media_ilha.sort_values(by='Bipes/hora', ascending=False).head(5)
        media_homem_hora_ilha = df_media_ilha['Bipes/hora'].head(5).mean()

        # Dados formatados para o card
        total_bipes = (f'{total_bipes:,.2f}'.replace(',', 'X').replace('.', ',').
                       replace('X', '.'))
        total_caixas = (f'{total_caixas:,.2f}'.replace(',', 'X').replace('.', ',').
                        replace('X', '.'))

        total_unidades = (f'{total_unidades:,.2f}'.replace(',', 'X').replace('.', ',').
                          replace('X', '.'))

        media_homem_hora_box = 0 if pd.isna(media_homem_hora_box) else (f"{media_homem_hora_box:,.2f}".
                                                                        replace(',', 'X').
                                                                        replace('.', ',').
                                                                        replace('X', '.'))

        media_homem_hora_ilha = 0 if pd.isna(media_homem_hora_ilha) else (f"{media_homem_hora_ilha:,.2f}".
                                                                          replace(',', 'X').
                                                                          replace('.', ',').
                                                                          replace('X', '.'))

        with col1:
            st.markdown(f"""
                <div style="background-color:#e9f7fd; height: 200px; padding:20px; border-radius:10px;
                border: 1.5px solid #94a8b0; box-shadow:0 2px 4px #6a787e;">
                    <h5>Bipe Homem-Hora</h5>
                    <p style="font-size:20px; font-weight:bold; color:#8d2ce9;">Box {media_homem_hora_box}</p>
                    <p style="font-size:20px; font-weight:bold; color:#1ea362;">Ilha {media_homem_hora_ilha}</p>
                    <p style="color:#151819;">Atualizado às {datetime.today().strftime('%H:%M')}</p>
                </div>
            """, unsafe_allow_html=True)

        with col2:
            st.markdown(f"""
                <div style="background-color:#e9f7fd; height: 200px; padding:20px; border-radius:10px;
                border: 1.5px solid #94a8b0; box-shadow:0 2px 4px #6a787e;">
                    <h5>Apanhas</h5>
                    <p style="font-size:28px; font-weight:bold; color:#e98d2c;">{total_bipes}</p>
                    <p style="color:#151819;">Atualizado às {datetime.today().strftime('%H:%M')}</p>
                </div>
            """, unsafe_allow_html=True)

        with col3:
            st.markdown(f"""
                <div style="background-color:#e9f7fd; height: 200px; padding:20px; border-radius:10px;
                border: 1.5px solid #94a8b0; box-shadow:0 2px 4px #6a787e;">
                    <h5>Total de caixas separadas</h5>
                    <p style="font-size:28px; font-weight:bold; color:#e98d2c;">{total_caixas}</p>
                    <p style="color:#151819;">Atualizado às {datetime.today().strftime('%H:%M')}</p>
                </div>
            """, unsafe_allow_html=True)

        with col4:
            st.markdown(f"""
                <div style="background-color:#e9f7fd; height: 200px; padding:20px; border-radius:10px;
                border: 1.5px solid #94a8b0; box-shadow:0 2px 4px #6a787e;">
                    <h5>Total de unidades separadas</h5>
                    <p style="font-size:28px; font-weight:bold; color:#e98d2c;">{total_unidades}</p>
                    <p style="color:#151819;">Atualizado às {datetime.today().strftime('%H:%M')}</p>
                </div>
            """, unsafe_allow_html=True)

    def mostrar_graficos(self, df_filtrado):
        st.markdown("---")
        col1, col2 = st.columns(2)

        with col1:
            with st.container(border=True):
                st.subheader('📈 Bipes por Dia')
                df_dia = df_filtrado.groupby('Dia')['Bipes'].sum().reset_index()
                fig = px.bar(df_dia, x='Dia', y='Bipes', text='Bipes', color_discrete_sequence=['#555555'])
                fig.update_layout(xaxis_title='Dia', yaxis_title='Total de Bipes', xaxis=dict(
                    tickmode='array', tickvals=df_dia['Dia'].tolist(), ticktext=df_dia['Dia'].tolist()))
                fig.update_traces(textposition='outside')
                st.plotly_chart(fig)

        with col2:
            with st.container(border=True):
                st.subheader('🕒 Produção Hora a Hora')
                df_horas = df_filtrado.groupby('Hora Operacional')['Bipes'].sum().reset_index()
                rotulos = {i: f'{(i + 6) % 24:02}h' for i in range(24)}
                df_horas['Hora Label'] = df_horas['Hora Operacional'].map(rotulos)
                fig = px.bar(df_horas, x='Hora Label', y='Bipes', text='Bipes', color_discrete_sequence=['#02a9f7'])
                fig.update_layout(xaxis_title='Hora do turno', yaxis_title='Bipes')
                fig.update_traces(textposition='outside')
                st.plotly_chart(fig)

    def mostrar_tabela(self, df_filtrado):
        col1, col2 = st.columns(2)

        lista_colunas_milhar = ['Bipes', 'Unidades', 'Caixas']

        # Editando apresentação da tabela box
        df_box = df_filtrado[df_filtrado['Tipo separação'] == 'Box']
        df_box = (df_box.groupby(['Código funcionário', 'Funcionário']).
                  agg({'Bipes': 'sum', 'Unidades': 'sum', 'Caixas': 'sum', 'Tempo': 'sum'}).
                  reset_index().sort_values(by='Bipes', ascending=False))
        df_box['Tempo'] = pd.to_timedelta(df_box['Tempo'], unit='s').apply(lambda x: str(x).split()[-1])

        for i in lista_colunas_milhar:
            df_box[i] = df_box[i].apply(lambda x: f'{x:,.2f}'.replace(',', 'X').
                                        replace('.', ',').replace('X', '.'))

        # Editando apresentação da tabela ilha
        df_ilha = df_filtrado[df_filtrado['Tipo separação'] == 'Ilha']
        df_ilha = (df_ilha.groupby(['Código funcionário', 'Funcionário']).
                   agg({'Bipes': 'sum', 'Unidades': 'sum', 'Caixas': 'sum', 'Tempo': 'sum'}).
                   reset_index().sort_values(by='Bipes', ascending=False))
        df_ilha['Tempo'] = pd.to_timedelta(df_ilha['Tempo'], unit='s').apply(lambda x: str(x).split()[-1])

        for i in lista_colunas_milhar:
            df_ilha[i] = df_ilha[i].apply(lambda x: f'{x:,.2f}'.replace(',', 'X').
                                          replace('.', ',').replace('X', '.'))
        with st.container(border=True):
            with col1:
                st.subheader('📋 Produção box')
                st.dataframe(df_box, use_container_width=True, hide_index=True)

        with st.container(border=True):
            with col2:
                st.subheader('📋 Produção ilha')
                st.dataframe(df_ilha, use_container_width=True, hide_index=True)

    def criar_dashboard(self):

        st.markdown(
            """
            <style>
            .main {
                background-color: #d4f0fc;  /* Defina a cor que desejar aqui */
            }
            </style>
            """,
            unsafe_allow_html=True
        )

        st.title('📊 Análise de produtividade CCH')

        # Criar os filtros
        mes_ano, funcionario, tipo_separacao, dia = self.criar_filtros()

        # Aplicar os filtros aos dados
        df_filtrado = self.aplicar_filtros(mes_ano, funcionario, tipo_separacao, dia)

        # Mostrar os cards e gráficos com os dados filtrados
        self.mostrar_cards(df_filtrado)
        self.mostrar_graficos(df_filtrado)
        self.mostrar_tabela(df_filtrado)


relatorio = Relatorios(nome_arquivo='Produtividade operação.xlsx')
dados = relatorio.tratar_dados()
dashboard = Dashboard(dados)
dashboard.criar_dashboard()
