class SelectParameters:  # Select API中参数名常量，参数名是大小写敏感的。具体含义参加api.py中的介绍
    CsvHeaderInfo = "CsvHeaderInfo"
    CommentCharacter = "CommentCharacter"
    RecordDelimiter = "RecordDelimiter"
    OutputRecordDelimiter = "OutputRecordDelimiter"
    FieldDelimiter = "FieldDelimiter"
    OutputFieldDelimiter = "OutputFieldDelimiter"
    QuoteCharacter = "QuoteCharacter"
    SplitRange = "SplitRange"
    LineRange = "LineRange"
    CompressionType = "CompressionType"
    KeepAllColumns = "KeepAllColumns"
    OutputRawData = "OutputRawData"
    EnablePayloadCrc = "EnablePayloadCrc"
    OutputHeader = "OutputHeader"
    SkipPartialDataRecord = "SkipPartialDataRecord"
    MaxSkippedRecordsAllowed = "MaxSkippedRecordsAllowed"
    AllowQuotedRecordDelimiter = "AllowQuotedRecordDelimiter"
    Json_Type = "Json_Type"
    ParseJsonNumberAsString = "ParseJsonNumberAsString"
    OverwriteIfExists = "OverwriteIfExists"
    AllowQuotedRecordDelimiter = "AllowQuotedRecordDelimiter"


class SelectJsonTypes:  # Select JSOn API中 Json_Type的合法值，大小写敏感。
    DOCUMENT = "DOCUMENT"
    LINES = "LINES"
